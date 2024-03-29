from setuptools import setup


SHORT_DESCRIPTION = 'Links to headings with extra magic'

try:
    with open('README.md', encoding='utf8') as readme:
        LONG_DESCRIPTION = readme.read()

except FileNotFoundError:
    LONG_DESCRIPTION = SHORT_DESCRIPTION


setup(
    name='foliantcontrib.superlinks',
    description=SHORT_DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    version='1.0.12',
    author='Daniil Minukhin',
    author_email='ddddsa@gmail.com',
    packages=['foliant.preprocessors.superlinks'],
    license='MIT',
    platforms='any',
    install_requires=[
        'foliant>=1.0.8',
        'foliantcontrib.meta>=1.3.0',
        'foliantcontrib.anchors>=1.0.4',
        'foliantcontrib.utils>=1.0.2',
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Documentation",
        "Topic :: Utilities",
    ]
)
