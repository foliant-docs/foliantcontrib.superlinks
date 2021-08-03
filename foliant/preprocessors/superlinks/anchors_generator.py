import re

from pathlib import Path
from pathlib import PosixPath

from foliant.contrib.header_anchors import make_unique
from foliant.contrib.header_anchors import to_id

SKIP = '{#_}'


class TitleNotFoundError(Exception):
    pass


class NotAChapterException(Exception):
    pass


class Titles:
    '''
    Class holding all the titles and their anchors in the Foliant project.

    The most important attribute is `chapters`, it is a dictionary:
    {
        chapter absolute path: {
            title: [list of anchors]
        }
    }

    The most important method is `add_chapter` which parses and adds the chapter
    to the class.
    '''
    FLAT_BACKENDS = ['pandoc', 'slate', 'aglio', 'mdtopdf']

    def __init__(self, backend: str, flat: bool or None = None):
        self.backend = backend
        if flat is None:
            self.flat = backend in self.FLAT_BACKENDS
        else:
            self.flat = flat
        self.chapters = {}
        self._accumulated_anchors = {}

    def add_chapter(self, filepath: str or PosixPath):
        '''
        Add a chapter to self.chapters dict under the key of absolute path to
        the chapter. Value of the dict is a dictionary with titles and unique
        anchors, returned by finalize_anchors function.

        :param filepath: path to chapter.
        '''
        def extend_anchors(orig: dict, add: dict):
            '''
            Extend the accumulated `orig` dict with basic anchors
            {anchor: list of titles} with new chapter dictionary `add`:

            if anchor is not present, it is added with all its titles,
            if anchor is already present, then list of titles is extended with
            new titles.
            '''
            for k, v in add.items():
                orig.setdefault(k, []).extend(v)

        abs_path = Path(filepath).resolve()
        if not abs_path.exists():
            raise FileNotFoundError(f'{filepath} does not exist!')
        basic_anchors, custom_ids = get_basic_anchors(abs_path, self.backend)
        title_ids = finalize_anchors(basic_anchors,
                                     self._accumulated_anchors if self.flat else {},
                                     self.backend)
        # overwrite customids
        for anchor, titles in custom_ids.items():
            for title in titles:
                title_ids[title] = [anchor]
        self.chapters[str(abs_path)] = title_ids
        extend_anchors(self._accumulated_anchors, basic_anchors)

    def get_id(self,
               filepath: str or PosixPath,
               title: str,
               occurrence: int = 1) -> str:
        '''
        Get id for title of the chapter defined by `filepath`. If there are
        duplicate heading titles in the document, you can pick the specific one
        by specifying occurence number.

        :param filepath: path to chapter where the title is located
        :param title: title to get the id of.
        :param occurence: number of the occurrence to pick.

        :returns: (id of the requested title, pos).
        '''
        abs_path = Path(filepath).resolve()
        if str(abs_path) not in self.chapters:
            raise NotAChapterException(f'{filepath} is not a chapter, can\'t process link')
        chapter_titles = self.chapters[str(abs_path)]

        if title not in chapter_titles:
            raise TitleNotFoundError(f'Title {title} missing in chapter {filepath}')
        return chapter_titles[title][occurrence - 1]


def get_basic_anchors(filepath: str or PosixPath,
                      backend: str) -> (dict, dict):
    '''
    Generate basic anchors for all titles in the `filepath`. Basic means that
    these anchors are not checked for duplicates, they are just converted from
    titles into id-strings.

    :param filepath: path to file where the titles will be searched.
    :param backend: name of the backend for which the anchors are generated.

    :returns: tuple with two dictionaries:
    (
        {anchor: list of titles which convert into this anchor},
        {custom_id: list of titles with this custom_id}
    )
    '''
    pattern = re.compile(r'^(?P<hashes>\#{1,6})\s+(?P<title>.+?)\s+(?:\{\#(?P<custom_id>\S+)\})?\s*$',
                         re.MULTILINE)
    basic_ids = {}
    custom_ids = {}
    with open(filepath) as f:
        for m in pattern.finditer(f.read()):
            title = m.group('title')
            custom_id = m.group('custom_id')
            anchor = to_id(title, backend)
            if custom_id:
                custom_ids.setdefault(custom_id, []).append((title, m.end()))
                # customids don't replace title anchor but add a div above
                # so the heading will still affect dublicate anchor generation
                # basic_ids.setdefault(anchor, []).append((SKIP, -1))
                basic_ids.setdefault(anchor, []).append((title, m.end()))
            else:
                basic_ids.setdefault(anchor, []).append((title, m.end()))
    return basic_ids, custom_ids


def finalize_anchors(basic: dict,
                     accumulated: dict,
                     backend: str) -> dict:
    '''
    Make all basic anchors from the `basic` dict unique. Uniqueness is defined
    with the use of `accumulated` dict, which contains all anchors from all files
    BEFORE this one (only needed for flat backends).

    :param basic: dictionary with basic anchors, returned by get_basic_anchors.
    :param accumulated: dictionary with all basic anchors BEFORE this file.
    :param backend: name of the backend.

    :returns: dict with {title: list of anchors for this title}

    * the value of the dict is a _list_ of titles because of duplicate titles.
      Now it is only used by meta links.
    '''
    result = {}
    for anchor, titles in basic.items():
        occurence = 0
        for title in titles:
            occurence += 1
            if title[0] == SKIP:
                continue  # custom_id title
            accum_count = len(accumulated.get(anchor, []))
            result.setdefault(title[0], []).append(
                (
                    make_unique(anchor, occurence + accum_count, backend),
                    title[1]
                )
            )
    return result
