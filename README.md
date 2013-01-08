Serpentarium
============

Serpentarium is a Sublime Text 2 plugin for work with ctags in Python files.

Install
-------

First, install ctags.

* OS X:

		brew install ctags

* Linux & Windows:

		follow your system user manual


Second, download the latest source from [GitHub](https://github.com/dreadatour/Serpentarium/zipball/master) and copy *Serpentarium* folder to your ST2 "Packages" directory.

Or clone the repository to your ST2 "Packages" directory:

    git clone git://github.com/dreadatour/Serpentarium.git


The "Packages" directory is located at:

* OS X:

        ~/Library/Application Support/Sublime Text 2/Packages/

* Linux:

        ~/.config/sublime-text-2/Packages/

* Windows:

        %APPDATA%/Sublime Text 2/Packages/

Features / Usage
----------------

Right-click on your project folder in sidebar menu and choose "Serpentarium: Setup project".
Right-click on your project folder in sidebar menu and choose "Serpentarium: Rebuild tags".

Now, use 'ctrl+]' for go to function under cursor definition and 'ctrl_[' for jump back.
Also, you can use 'ctrl+;' for search for definitions in whole project.
