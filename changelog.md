# 1.0.11

- Fix imports.

# 1.0.10

- New utils module.

# 1.0.9

- Fix: BOF anchors bug
- Fix: common paths processing

# 1.0.8

- Fix: proper relative path generation for links.
- Fix: multiple issues when !path modifier is used in the link tag.
- BOF anchors now won't be added for mkdocs backend.

# 1.0.7

- If tag body it empty, superlinks will try to guess the right caption of the link:
    - referenced title for links by title,
    - meta section title for links by meta section,
    - heading title for links by CustomIDs,
    - title from config or first heading title in the file for links to file,
    - anchor name for links by anchors.

# 1.0.6

- Improved Confluence links: if section is not uploaded to Confluence, reference to overall project (if it is uploaded to Confluence).

# 1.0.5

- New: added Confluence backend support.
- Fix: links were corrupted when customids were used.
- Fix: several other bug fixes and optimizations.

# 1.0.4

- Fix: bug with chapters.

# 1.0.3

- Support meta 1.3.

# 1.0.2

- add dependencies order check.
- rename anchor parameter to id.
- add anchor parameter for possibly global anchor search.
- link to anchors in Confluence are now partly supported.

# 1.0.1

- Initial release.
