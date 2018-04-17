.. _installation:

Installation
============

Prerequisites
-------------

Reynir runs on **CPython 3.4** or newer, and on **PyPy 3.5**
or newer (more info on PyPy `here <http://pypy.org/>`_).

On GNU/Linux and similar systems, you may need to have ``python3-dev`` and/or
potentially ``python3.6-dev`` (or other version corresponding to your Python
interpreter) installed on your system::

    # Debian or Ubuntu:
    $ sudo apt-get install python3-dev
    $ sudo apt-get install python3.6-dev

On Windows, you need the `Visual Studio Build Tools 2017 <http://landinghub.visualstudio.com/visual-cpp-build-tools>`_,
specifically the Visual C++ build tools, installed on your PC along with the Windows 10 SDK.

Install with pip
----------------

To install Reynir::

    $ pip install reynir

...or if you have both Python2 and Python3 available on your system::

    $ pip3 install reynir

...or if you want to be able to edit Reynir's source code in-place
and perhaps submit pull requests (welcome!) to the project's
`GitHub repository <https://github.com/vthorsteinsson/ReynirPackage>`_::

    $ mkdir ~/github
    $ cd ~/github
    $ git clone https://github.com/vthorsteinsson/ReynirPackage
    $ cd ReynirPackage
    $ python setup.py develop


On the most common Linux x86_64/amd64 systems, ``pip`` will download and install a binary wheel.
On other systems, a source distribution will be downloaded and compiled to binary.


Install into a virtualenv
-------------------------

In many cases, you will want to maintain a separate Python environment for
your project that uses Reynir. For this, you can use *virtualenv*::

    $ virtualenv -p python3 venv

    # Enter the virtual environment
    $ source venv/bin/activate

    # Install reynir
    $ pip install reynir

    $ python
        [ Use Python with reynir ]

    # Leave the virtual environment
    $ deactivate


More information about virtualenv is `available here <https://virtualenv.pypa.io/en/stable/>`_.
