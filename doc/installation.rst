.. _installation:

Installation
============

Prerequisites
-------------

Reynir runs on **CPython 3.4** or newer, and on **PyPy 3.5**
or newer. PyPy is recommended for best performance.

You may need to have ``python3-dev`` and/or potentially ``python3.6-dev`` (or other
version corresponding to your Python interpreter) installed on your system::

    # Debian or Ubuntu:
    $ sudo apt-get install python3-dev
    $ sudo apt-get install python3.6-dev


Install with pip
----------------

To install Reynir::

    $ pip install reynir

    # ...or if you have both Python2 and Python3 available on your system:
    $ pip3 install reynir


On the most common Linux x86_64/amd64 systems, this will download and install a binary wheel.
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

    # [ Use Python with reynir ]

    # Leave the virtual environment
    $ deactivate


More information about virtualenv is `available here <https://virtualenv.pypa.io/en/stable/>`_.
