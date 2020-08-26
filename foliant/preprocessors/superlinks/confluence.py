from pathlib import Path, PosixPath
from logging import getLogger
from foliant.meta.generate import get_meta_for_chapter


logger = getLogger('flt.superlinks.confluence')


class BadParamsException(Exception):
    pass


def construct_confluence_link(text: str,
                              pos: int,
                              filepath: str or PosixPath or None = None,
                              anchor: str or None = None,
                              context: dict = {}):
    logger.info(
        'Constructing confluence link:'
        f'\ntext: "{text}"'
        f'\npos: "{pos}"'
        f'\nfilepath: "{filepath}"'
        f'\nanchor: "{anchor}"'
    )
    result = None
    if filepath is None and anchor is None:
        raise BadParamsException(
            'Cannot generate confluence link: page title or anchor are required'
        )
    chapter_name = str(Path(filepath).relative_to(context['config']['tmp_dir']))
    chapter = get_meta_for_chapter(filepath, chapter_name)
    if chapter.name in context['config'].get('chapters', []):
        section = chapter.get_section_by_offset(pos)
    else:
        section = None
    logger.info(f'Section: {section}')
    title, id_ = get_page_title_or_id(section, context)
    if title or id_:
        result = gen_link(text, title, id_, anchor)
    logger.info(f'Constructed confluence link:\n{result}')
    return result


def get_page_title_or_id(section, context) -> tuple:
    config_data = context['config']['backend_config']['confluence']
    config_id, config_title = None, None
    if 'id' in config_data:
        config_id = config_data['id']
    elif 'title' in config_data and 'space_key' in config_data:
        config_title = config_data['title']

    cur_section = section

    while cur_section is not None:
        if 'confluence' in cur_section.data:
            break
        cur_section = cur_section.parent
    else:
        logger.info('This section or its parents are not uploaded to confluence'
                    f', returning global id or title: {config_title}, {config_id}')
        return config_title, config_id

    section_data = cur_section.data.get('confluence')

    if 'id' in section_data:
        return None, section_data['id']
    else:
        if 'title' in section_data:
            return section_data['title'], None
        else:
            return cur_section.title, None


def gen_link(text: str,
             title: str or None = None,
             id_: int or None = None,
             anchor: str or None = None):
    result = '<raw_confluence>\n'

    if anchor:
        result += f'    <ac:link ac:anchor="{anchor}">\n'
    else:
        result += '    <ac:link>\n'

    if title:
        result += f'        <ri:page ri:content-title="{title}"/>\n'
    elif id_:
        result += f'        <ri:content-entity ri:content-id="{id_}"/>\n'

    result += (
        f'        <ac:plain-text-link-body><![CDATA[{text}]]></ac:plain-text-link-body>\n'
        '    </ac:link>\n</raw_confluence>'
    )
    return result
