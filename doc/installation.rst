.. _installation:

Installation
============

Prerequisites
-------------

Reynir runs on **CPython 3.4** or newer, and on **PyPy 3.5**
or newer (more info on PyPy `here <http://pypy.org/>`_).

On GNU/Linux and similar systems, you may need to have ``python3-dev`` and/or
potentially ``python3.6-dev`` (or other version corresponding to your Python
interpreter) installed on your system:

.. code-block:: bash

    # Debian or Ubuntu:
    $ sudo apt-get install python3-dev
    $ sudo apt-get install python3.6-dev

On Windows, you may need the latest
`Visual Studio Build Tools <https://www.visualstudio.com/downloads/?q=build+tools+for+visual+studio>`_,
specifically the Visual C++ build tools, installed on your PC along
with the Windows 10 SDK.

Install with pip
----------------

To install Reynir:

.. code-block:: bash

    $ pip install reynir

...or if you have both Python2 and Python3 available on your system:

.. code-block:: bash

    $ pip3 install reynir

...or if you want to be able to edit Reynir's source code in-place
and perhaps submit pull requests (welcome!) to the project's
`GitHub repository <https://github.com/vthorsteinsson/ReynirPackage>`_:

.. code-block:: bash

    $ mkdir ~/github
    $ cd ~/github
    $ git clone https://github.com/vthorsteinsson/ReynirPackage
    $ cd ReynirPackage
    $ python setup.py develop

On the most common Linux x86_64/amd64 systems, ``pip`` will download and
install a binary wheel. On other systems, a source distribution will be
downloaded and compiled to binary.


Install into a virtualenv
-------------------------

In many cases, you will want to maintain a separate Python environment for
your project that uses Reynir. For this, you can use *virtualenv*
(if you haven't already, install it with ``pip install virtualenv``):

.. code-block:: bash

    $ virtualenv -p python3 venv

    # Enter the virtual environment
    $ source venv/bin/activate

    # Install reynir into it
    $ pip install reynir

    $ python
        [ Use Python with reynir ]

    # Leave the virtual environment
    $ deactivate

On Windows:

.. code-block:: batch

    C:\MyProject> virtualenv venv

    REM Enter the virtual environment
    C:\MyProject> venv/Scripts/activate

    REM Install reynir into it
    (venv) C:\MyProject> pip install reynir

    (venv) C:\MyProject> python
        REM [ Use Python with reynir ]

    REM Leave the virtual environment
    (venv) C:\MyProject> deactivate

More information about *virtualenv* is `available
here <https://virtualenv.pypa.io/en/stable/>`_.
