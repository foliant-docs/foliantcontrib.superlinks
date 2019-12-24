[![](https://img.shields.io/pypi/v/foliantcontrib.superlinks.svg)](https://pypi.org/project/foliantcontrib.superlinks/)

# SuperLinks for Foliant

This preprocessor extends the functionality of Markdown links, allowing you to reference by the heading title, file name or meta id. It works correctly with most backends, resolving to proper links, depending on which backend is being used.

It adds the `<link>` tag.

## The Problem

The problem with Markdown links is that you have to specify the correct anchor and file path right away.

Let's imagine that you want to create a link to a heading which is defined in another chapter.

If you are building a single-page PDF with Pandoc, you will only need to specify the anchor, which Pandoc generates from that title. But if you are building an MkDocs website, you will need to specify the relative filename to the referenced chapter, and the anchor, which MkDocs generates from the titles. By the way, Pandoc and MkDocs generate anchors differently. So there's no way to make it work for all backends by using just Markdown link syntax.

Superlinks aim to solve this problem.

## Installation

Install the preprocessor:

```bash
$ pip install foliantcontrib.superlinks
```

## Config

To enable the preprocessor, add `superlink` to `preprocessors` section in the project config.

```yaml
preprocessors:
    - superlinks
```

The preprocessor has no config options just now. But it has some important tag options.

## Usage

To add a link, use a `link` tag with a combination of following parameters:

`title`
:    Heading title, which you want to create a link to.

`src`
:    Relative path to a chapter which is being referenced.

`meta_id`
:    ID of the meta section which is being referenced. (if `title` is used, then this title MUST be inside this meta section)

`anchor`
:    Name of the anchor defined by [Anchors](../anchors.md) preprocessor or an ID defined by [CustomIDs](../customids.md) preprocessor. If `src` or `meta` is not provided — the id will be searched globally.

`id`
:    Just a hardcoded id. No magic here.

## Examples

**Reference a title in the same document**

```html
<link title="My title">Link caption</link>
```

**Reference a title in another chapter**

```html
<link src="subfolder/another_chapter.md" title="Another title">Link caption</link>
```

**Reference the beginning of another chapter**

```html
<link src="subfolder/another_chapter.md">Link caption</link>
```

**Reference a title inside meta section**

```html
<link meta_id="SECTION1" title="Title in section1">Link caption</link>
```

**Reference the beginning of meta section**

```html
<link meta_id="SECTION1">Link caption</link>
```

**Reference an anchor and search for it globally**

```html
<link anchor="my_anchor">Link caption</link>
```

**Reference an anchor and search for it in specific chapter**

```html
<link src="subfolder/another_chapter.md" anchor="my_anchor">Link caption</link>
```

## Supported Backends:

Backend | Support
------- | -------
aglio | ✅ YES
pandoc | ✅ YES
mdtopdf | ✅ YES
mkdocs | ✅ YES
slate | ✅ YES
confluence | ❌ NOt yet
