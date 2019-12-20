'''
Preprocessor for Foliant documentation authoring tool.
Generates documentation from RAML spec file.
'''
import re
import random

from pathlib import Path, PosixPath

from foliant.preprocessors.utils.preprocessor_ext import (BasePreprocessorExt,
                                                          allow_fail)
from foliant.preprocessors.utils.combined_options import Options

from foliant.meta_commands.generate.generate import load_meta
from foliant.preprocessors import anchors
from .anchors_generator import Titles, TitleNotFoundError


def construct_link(filepath: str or Path, anchor: str, caption: str = ''):
    '''
    Construct Mardown link from its components.

    :param filepath: path to file which is being referenced (relative to
                     current md-file!)
    :param anchor:   anchor to id on the page.
    :param caption:  link caption.

    :returns: string with constructed Markdown link.

    '''
    processed_anchor = anchor[1:] if anchor.startswith('#') else anchor
    if processed_anchor:
        processed_anchor = '#' + processed_anchor
    link_template = f'[{caption}]({filepath}#{anchor})'
    return link_template


class Preprocessor(BasePreprocessorExt):
    tags = ('link',)

    defaults = {
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = self.logger.getChild('superlinks')
        self.logger.debug(f'Preprocessor inited: {self.__dict__}')

        self.anchors = Titles(self.context['backend'])
        for chapter in self.config['chapters']:
            self.anchors.add_chapter(self.working_dir / chapter)

        self.meta = load_meta(self.config['chapters'], self.working_dir)

        self.bof_anchors = {}

    def _rel_to_current(self, filepath: str or PosixPath) -> PosixPath:
        '''Get a path relative to current processing file.'''
        return Path(filepath).relative_to(self.current_filepath.parent)

    def _get_bof_anchor(self, filepath: str or PosixPath):
        '''
        If file is already in the mapping of BOF-anchors (self.bof_anchors) —
        return its id.
        If file is not yet in the mapping — generate a unique ID and, save it in
        the mapping and return this ID.

        :param filepath: path to file which is being referenced.

        :returns: unique id of the anchor at the beginning of the file.
        '''

        abs_path = str(Path(filepath).resolve())
        return self.bof_anchors.setdefault(abs_path, hex(random.getrandbits(64))[2:-1])

    def _get_link_by_title(self,
                           filepath: str or PosixPath,
                           title: str,
                           caption: str) -> str:
        '''
        Generate proper anchor from the title and return Markdown link to it.

        :param filepath: path to file which is being referenced.
        :param title: title which is being referenced.
        :param caption: link caption.

        :returns: string with Markdown link to needed title.
        '''

        anchor = self.anchors.get_id(filepath, title)
        return construct_link(self._rel_to_current(filepath), anchor, caption)

    def _get_link_to_bof(self,
                         filepath: str or PosixPath,
                         caption: str) -> str:
        '''
        Get link to beginning of the file. At the beginning of chapters which
        are referenced without anchors, a special anchor will be added.
        This method returns the link to this anchor.

        :param filepath: path to file which is being referenced.
        :param caption: link caption.

        :returns: string with Markdown link to the beginning of the file.
        '''
        anchor = self._get_bof_anchor(filepath)
        return construct_link(self._rel_to_current(filepath), anchor, caption)

    def _get_link_by_meta(self,
                          meta_id: str,
                          title: str or None,
                          caption: str) -> str:
        '''
        Get link to meta section.

        If title is specified preprocessor will search
        for this title only in this meta section and return error if it's not
        found there. But if it _is_ inside the meta section, the link will be
        pointing at it even if there are other headings with the same title in
        the document.

        If the title is not specified, then link will be pointing at the
        beginning of the meta section.

        :param meta_id: ID of the meta section, which is being referenced.
        :param title: title, which is being referenced (MUST be located inside
                      the meta section!)
        :param caption: link caption.

        :returns: string with Markdown link to the the meta section.
        '''
        section = self.meta.get_by_id(meta_id)
        filepath = section.chapter.filename
        section_source = section.get_source(False)
        if title:
            pattern = re.compile(r'^\#{1,6}\s+' +
                                 title +
                                 r'\s+(?:\{\#(?P<custom_id>\S+)\})?\s*$',
                                 re.MULTILINE)
            match = pattern.search(section_source)
            if match is None:
                raise TitleNotFoundError(f'Title "{title}" not found in meta section with id {meta_id}')
            start = section.start + match.start()
        else:
            # title is not specified. Means should link to the beginning of section
            if section.is_main():
                # main section may not start with a title so just link to BOF
                return self._get_link_to_bof(filepath, caption)
            else:
                # all subsections start with a title, so we can determine it
                title_pattern = re.compile(r'^\#{1,6}\s+' +
                                           r'(?P<title>.+?)' +
                                           r'\s+(?:\{\#(?P<custom_id>\S+)\})?\s*$',
                                           re.MULTILINE)
                title_match = title_pattern.search(section_source)
                title = title_match.group('title')
                start = section.start + title_match.start()
                pattern = re.compile(r'^\#{1,6}\s+' +
                                     title +
                                     r'\s+(?:\{\#(?P<custom_id>\S+)\})?\s*$',
                                     re.MULTILINE)
        occurence = 0
        for m in pattern.finditer(section.chapter.main_section.get_source(False)):
            if m.start() < start:
                occurence += 1
            else:
                break
        anchor = self.anchors.get_id(filepath, title, occurence)
        return construct_link(self._rel_to_current(filepath), anchor, caption)

    @allow_fail()
    def process_links(self, block) -> str:
        '''Process a link tag and replace it with Markdown link to proper anchor'''
        self.logger.debug(f'Processing link {block.group(0)}')

        tag_options = Options(self.get_options(block.group('options')))
        caption = block.group('body')
        if 'src' in tag_options:
            # src in tag is relative to file where it's mentioned
            filepath = self.current_filepath.parent / tag_options['src']
        elif 'meta_id' in tag_options:  # try get filepath from meta
            filepath = self.meta.get_by_id(tag_options['meta_id']).chapter.filename
        else:  # assume that current file is being referenced
            filepath = self.current_filepath
        title = tag_options.get('title')
        anchor = tag_options.get('anchor')
        self.logger.debug(f'Derrived filepath: {filepath}')
        if anchor:
            self.logger.debug(f'Anchor specified, constructing link right away')
            return construct_link(self._rel_to_current(filepath), anchor, caption)
        elif 'meta_id' in tag_options:
            self.logger.debug(f'meta_id specified, looking for title in section')
            return self._get_link_by_meta(tag_options['meta_id'], title, caption)
        elif title:
            self.logger.debug(f'Title specified, looking for title in file')
            return self._get_link_by_title(filepath, title, caption)
        else:
            self.logger.debug(f'Niether title, nor anchor are specified, linking to beginning of file')
            return self._get_link_to_bof(filepath, caption)

    def _add_bof_anchors(self):
        '''
        Add anchors to the beginning of all files which are referenced without
        anchors.

        The IDs for these anchors are generated randomly and are quite unique.

        Preprocessor foliantcontrib.anchors is used to generate the anchor element.
        '''
        if not self.bof_anchors:
            return

        anchors_options = {}
        preprocessors = self.config.get('preprocessors', [])
        for p in preprocessors:
            if isinstance(p, dict) and 'anchors' in p:
                anchors_options = p['anchors']
        anchors_preprocessor = anchors.Preprocessor(
            self.context,
            self.logger,
            self.quiet,
            self.debug,
            anchors_options
        )
        anchors_preprocessor.applied_anchors = []
        anchors_preprocessor.header_anchors = []

        for filename, anchor in self.bof_anchors.items():
            with open(filename) as f:
                content = f.read()

            start = 0

            if content.startswith('---\n'):
                # file starts with yfm, have to insert anchor after it
                yfm_end = content.find('\n---\n', 1)
                start = yfm_end + len('\n---\n') if yfm_end != -1 else 0
            elif content.startswith('#'):
                # file starts with title, better insert anchor after it
                start = content.find('\n', 1)

            anchor_str = anchors_preprocessor.process_anchors(f'\n\n<anchor>{anchor}</anchor>\n\n')
            processed_content = content[:start] + anchor_str + content[start:]

            with open(filename, 'w') as f:
                f.write(processed_content)

    def apply(self):
        self._process_tags_for_all_files(func=self.process_links)
        self._add_bof_anchors()
        self.logger.info('Preprocessor applied')
