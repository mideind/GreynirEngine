.. _installation:

Installation
============

Prerequisites
-------------

Greynir runs on **CPython 3.9** or newer, and on **PyPy 3.9**
or newer (more info on PyPy `here <http://pypy.org/>`_).

On GNU/Linux and similar systems, you may need to have ``python3-dev``
installed on your system:

.. code-block:: bash

    # Debian or Ubuntu:
    $ sudo apt-get install python3-dev

Depending on your system, you may also need to install ``libffi-dev``:

.. code-block:: bash

    # Debian or Ubuntu:
    $ sudo apt-get install libffi-dev

On Windows, you may need the latest
`Visual Studio Build Tools <https://www.visualstudio.com/downloads/?q=build+tools+for+visual+studio>`_,
specifically the Visual C++ build tools, installed on your PC along
with the Windows 10 SDK.


Install with pip
----------------

To install Greynir:

.. code-block:: bash

    $ pip install reynir

...or if you have both Python2 and Python3 available on your system:

.. code-block:: bash

    $ pip3 install reynir

...or if you want to be able to edit Greynir's source code in-place,
install ``git`` and do the following (note the final dot in the last line):

.. code-block:: bash

    $ mkdir ~/github
    $ cd ~/github
    $ git clone https://github.com/mideind/GreynirEngine
    $ cd GreynirEngine
    $ git pull
    $ pip install -e .

On most common Linux x86_64/amd64 systems, ``pip`` will download and
install a binary wheel. On other systems, a source distribution will be
downloaded and compiled to binary. This requires a standard, Python-supported
C/C++ compiler to be present on the system.

Greynir's binary wheels are in the ``manylinux2010`` format (or newer).
This means that you will need version 19.0 or newer of ``pip`` to be able
to install a Greynir wheel. Versions of Python from 3.7 onwards include a
new-enough ``pip``.

Pull requests are welcome in the project's
`GitHub repository <https://github.com/mideind/GreynirEngine>`_.


Install into a virtualenv
-------------------------

In many cases, you will want to maintain a separate Python environment for
your project that uses Greynir. For this, you can use *virtualenv*
(if you haven't already, install it with ``pip install virtualenv``):

.. code-block:: bash

    $ virtualenv -p python3 venv

    # Enter the virtual environment
    $ source venv/bin/activate

    # Install Greynir into it
    $ pip install reynir

    $ python
        [ Use Python with Greynir ]

    # Leave the virtual environment
    $ deactivate

On Windows:

.. code-block:: batch

    C:\MyProject> virtualenv venv

    REM Enter the virtual environment
    C:\MyProject> venv/Scripts/activate

    REM Install Greynir into it
    (venv) C:\MyProject> pip install reynir

    (venv) C:\MyProject> python
        REM [ Use Python with Greynir ]

    REM Leave the virtual environment
    (venv) C:\MyProject> deactivate

More information about *virtualenv* is `available
here <https://virtualenv.pypa.io/en/stable/>`_.
