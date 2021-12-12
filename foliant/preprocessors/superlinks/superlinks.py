'''
Preprocessor for Foliant documentation authoring tool.
Generates documentation from RAML spec file.
'''
import re
import os

from pathlib import Path, PosixPath
from hashlib import md5

from foliant.preprocessors.utils.preprocessor_ext import (BasePreprocessorExt,
                                                          allow_fail)
from foliant.contrib.combined_options import Options
from foliant.contrib.chapters import Chapters, ChapterNotFoundError
from foliant.contrib.utils import prepend_file

from foliant.meta.generate import load_meta
from foliant.preprocessors import anchors
from .anchors_generator import Titles, TitleNotFoundError
from .confluence import gen_link, construct_confluence_link


class AnchorNotFoundError(Exception):
    pass


def preprocessor_index(config: dict, preprocessor: str) -> int:
    '''Check if preprocessor is listed in config and return its index or -1'''
    i = 0
    for p in config.get('preprocessors', []):
        if isinstance(p, str):
            if p == preprocessor:
                return i
        elif isinstance(p, dict):
            if preprocessor in p:
                return i
        i += 1
    else:
        return -1


def src_to_tmp(
    filepath: str or PosixPath,
    src_path: str or PosixPath,
    tmp_path: str or PosixPath
):
    '''
    If filepath is an absolute path and is located in src_dir, convert it into
    working dir path. Return filepath otherwise.
    '''
    filepath_ = Path(filepath)
    src_path_ = Path(src_path).resolve()
    tmp_path_ = Path(tmp_path).resolve()
    if src_path_ in filepath_.parents:
        return tmp_path_ / filepath_.relative_to(src_path_)
    else:
        return filepath


def rel_path(filepath: str or PosixPath,
             rel_to: str or PosixPath) -> PosixPath:
    '''Get a path relative to `rel_to` file.'''
    target = Path(filepath).resolve()
    source = Path(rel_to).resolve()
    if target == source:
        return ''

    common = os.path.commonpath([target, source.parent])
    depth = len(source.relative_to(common).parent.parts)
    levelup = os.path.join(*['..'] * depth) if depth else '.'
    return levelup / target.relative_to(common)


def get_first_heading(filepath: str or PosixPath) -> str:
    pattern = re.compile(r'^.*?(?=^#{1,6} (?P<title>[^\n]+))',
                         flags=re.MULTILINE)
    with open(filepath, encoding='utf8') as f:
        match = pattern.search(f.read())
    if match:
        return match.group('title')
    else:
        return ''


class Preprocessor(BasePreprocessorExt):
    tags = ('link',)

    defaults = {
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = self.logger.getChild('superlinks')
        self.logger.debug(f'Preprocessor inited: {self.__dict__}')
        self.anchors = Titles(self.context['backend'])
        self.chapters = Chapters.from_config(self.config)
        for chapter in self.chapters.flat:
            self.anchors.add_chapter(self.working_dir / chapter)

        self.logger.debug(f'Generated anchors:\n{self.anchors.chapters}')
        self.meta = load_meta(self.config['chapters'], self.working_dir)

        self.bof_anchors = {}

    def _construct_link(self,
                        filepath: str or PosixPath,
                        anchor: str,
                        caption: str = '') -> str:
        '''
        Construct Markdown link from its components.

        :param filepath: path to file which is being referenced
        :param cur_file: path to current processed file
        :param anchor:   anchor to id on the page.
        :param caption:  link caption.

        :returns: string with constructed Markdown link.

        '''
        target_file = rel_path(
            filepath,
            self.current_filepath
        )
        processed_anchor = anchor[1:] if anchor.startswith('#') else anchor

        if processed_anchor:
            processed_anchor = '#' + processed_anchor
        return f'[{caption}]({target_file}{processed_anchor})'

    def _get_bof_anchor(self, filepath: str or PosixPath):
        '''
        If file is already in the mapping of BOF-anchors (self.bof_anchors) —
        return its id.
        If file is not yet in the mapping — generate a unique ID and, save it in
        the mapping and return this ID.

        :param filepath: path to file which is being referenced.

        :returns: unique id of the anchor at the beginning of the file.
        '''

        abs_path = Path(filepath).resolve()
        key = str(abs_path)
        if key in self.bof_anchors:
            return self.bof_anchors[key]

        rel_path = str(abs_path.relative_to(self.working_dir.resolve()))
        file_hash = md5(rel_path.encode()).hexdigest()[:8]
        self.bof_anchors[key] = file_hash
        return file_hash

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
        anchor, pos = self.anchors.get_id(filepath, title)
        link_caption = caption or title

        if self.context['backend'] == 'confluence':
            return construct_confluence_link(link_caption,
                                             pos=pos,
                                             filepath=filepath,
                                             anchor=anchor,
                                             context=self.context)
        else:
            return self._construct_link(filepath, anchor, link_caption)

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
        if caption:
            link_caption = caption
        else:
            try:
                chapter_name = self.chapters.get_chapter_by_path(filepath)
                chapter_title = self.chapters.get_chapter_title(chapter_name)
            except ChapterNotFoundError:
                # file may have been generated by some other preprocessor, you never know
                chapter_title = ''
            link_caption = chapter_title or get_first_heading(filepath)

        if self.context['backend'] == 'mkdocs':
            # for mkdocs bof anchors are not required
            return self._construct_link(filepath, '', link_caption)
        else:
            anchor = self._get_bof_anchor(filepath)
            if self.context['backend'] == 'confluence':
                return construct_confluence_link(link_caption,
                                                 pos=0,
                                                 filepath=filepath,
                                                 anchor=anchor,
                                                 context=self.context)
            else:
                return self._construct_link(filepath, anchor, link_caption)

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
            pattern = re.compile(
                r'^\#{1,6}\s+' + title + r'\s+(?:\{\#(?P<custom_id>\S+)\})?\s*$',
                re.MULTILINE
            )
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
                title_pattern = re.compile(
                    r'^\#{1,6}\s+(?P<title>.+?)\s+(?:\{\#(?P<custom_id>\S+)\})?\s*$',
                    re.MULTILINE
                )
                title_match = title_pattern.search(section_source)
                title = title_match.group('title')
                start = section.start + title_match.start()
                pattern = re.compile(
                    r'^\#{1,6}\s+' + title + r'\s+(?:\{\#(?P<custom_id>\S+)\})?\s*$',
                    re.MULTILINE
                )
        occurence = 1
        for m in pattern.finditer(section.chapter.main_section.get_source(False)):
            if m.start() < start:
                occurence += 1
            else:
                break
        anchor, pos = self.anchors.get_id(filepath, title, occurence)
        link_caption = caption or title
        if self.context['backend'] == 'confluence':
            return construct_confluence_link(link_caption,
                                             pos=pos,
                                             filepath=filepath,
                                             anchor=anchor,
                                             context=self.context)
        else:
            return self._construct_link(filepath, anchor, link_caption)

    def _get_link_by_anchor(self,
                            filename: str or PosixPath,
                            anchor: str,
                            caption: str) -> str:
        '''
        Search for anchor. If filename is not current path, then search in
        `filename` file. If it is current path, then search globally.

        :param filename: path to md-file where to look for anchor.
        :param anchor: anchor to look for.
        :param caption: caption of the link.

        :returns: constructed link string.
        '''

        if anchor not in self.applied_anchors:
            raise AnchorNotFoundError(f'Anchor {anchor} not found in the project')

        # if filename is current file, means that src was not provided. We will
        # perform global search in this case
        if filename != self.current_filepath:
            target_file = Path(filename)
            for file, pos, title in self.applied_anchors[anchor]:
                if file.resolve() == target_file.resolve():
                    break
            else:
                raise AnchorNotFoundError(f'Anchor {anchor} not found in {filename}')
        else:
            anchors = self.applied_anchors[anchor]
            if len(anchors) > 1:
                self._warning(f'Anchor {anchor} appears several times in project. '
                              'Picking the first occurrence')
            target_file, pos, title = anchors[0]
        link_caption = caption or title or anchor
        if self.context['backend'] == 'confluence':
            return construct_confluence_link(link_caption,
                                             pos=pos,
                                             filepath=target_file,
                                             anchor=anchor,
                                             context=self.context)
        return self._construct_link(target_file, anchor, link_caption)

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
        filepath = src_to_tmp(filepath, self.config['src_dir'], self.working_dir)
        title = tag_options.get('title')
        anchor = tag_options.get('anchor')
        id_ = tag_options.get('id')
        self.logger.debug(f'Derrived filepath: {filepath}')
        if id_:
            self.logger.debug(f'ID specified, constructing link right away')
            if self.context['backend'] == 'confluence':
                return gen_link(caption, anchor=id_)
            else:
                return self._construct_link(filepath, id_, caption)
        elif 'anchor' in tag_options:
            self.logger.debug(f'anchor specified, searching for global anchor')
            return self._get_link_by_anchor(filepath, anchor, caption)
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

        The IDs for these anchors are generated from the filename and are quite unique.

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
            # TODO: {} or not {}
            anchor_str = anchors_preprocessor.process_anchors(f'\n\n<anchor>{anchor}</anchor>\n\n', {})
            prepend_file(filename, anchor_str, before_yfm=False, before_heading=False)

    def collect_anchors(self):
        '''
        Search all md-files in working dir for <anchor> tags and custom_ids and
        save them into applied_anchors attibute of following structure:

        {
            'anchor_name': [
                (
                    PosixPath of file where it is mentioned,
                    pos[int] of the anchor,
                    title[str] of the heading with customid or None for anchor
                ), ...
            ]
        }
        '''

        anchor_pattern = re.compile(
            rf'(?<!\<)\<anchor(\s(?P<options>[^\<\>]*))?\>'
            rf'(?P<body>.*?)\<\/anchor\>',
            flags=re.DOTALL
        )
        customid_pattern = re.compile(
            r'^(?P<hashes>\#{1,6})\s+(?P<title>.+?)\s+'
            r'(?:\{\#(?P<custom_id>\S+)\})\s*$',
            re.MULTILINE
        )

        self.applied_anchors = {}
        for markdown_file_path in self.working_dir.rglob('*.md'):
            with open(markdown_file_path) as f:
                content = f.read()
                for m in anchor_pattern.finditer(content):
                    list_ = self.applied_anchors.setdefault(m.group('body'), [])
                    # if markdown_file_path not in list_:
                    list_.append((markdown_file_path, m.start(), None))
                for m in customid_pattern.finditer(content):
                    list_ = self.applied_anchors.setdefault(m.group('custom_id'), [])
                    # if markdown_file_path not in list_:
                    list_.append((markdown_file_path, m.start(), m.group('title')))
        self.logger.debug(f'Applied anchors dict:\n\n{self.applied_anchors}')

    def check_dependencies(self):
        '''
        - Check if customids preprocessor is listed after superlinks or raise a
        warning.
        - Check if anchors preprocessor is listed after superlinks or raise a
        warning.
        - Check if includes preprocessor is listed before superlinks or raise a
        warning.
        '''
        superlinks_index = preprocessor_index(self.config, 'superlinks')
        custom_ids_index = preprocessor_index(self.config, 'customids')
        anchors_index = preprocessor_index(self.config, 'anchors')
        includes_index = preprocessor_index(self.config, 'includes')

        if custom_ids_index != -1:
            if custom_ids_index < superlinks_index:
                self._warning('CustomIDs preprocessor should be listed AFTER '
                              'superlinks in config for magic to work')

        if anchors_index != -1:
            if anchors_index < superlinks_index:
                self._warning('Anchors preprocessor should be listed AFTER '
                              'superlinks in config for global anchor search to work')

        if includes_index != -1:
            if includes_index > superlinks_index:
                self._warning('Includes preprocessor should be listed BEFORE '
                              'superlinks in config, otherwise we do not guarantee anything')

    def apply(self):
        self.check_dependencies()
        self.collect_anchors()
        self._process_tags_for_all_files(func=self.process_links, buffer=True)
        self._add_bof_anchors()
        self.logger.info('Preprocessor applied')
