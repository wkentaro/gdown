gdown
=====

.. image:: https://travis-ci.org/wkentaro/gdown.svg?branch=master
    :target: https://travis-ci.org/wkentaro/gdown
.. image:: https://badge.fury.io/py/gdown.svg
    :target: https://badge.fury.io/py/gdown


Wget for files at Google Drive.


Usage
-----

.. code-block:: bash

  gdown "[URL]" -O [FILENAME]


**Example**

.. code-block:: bash

  gdown 'https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c'
  cat spam.txt  # spam


Installation
------------

**By apt**

.. code-block:: bash

  sudo add-apt-repository ppa:wkentaro/gdown
  sudo apt-get update
  sudo apt-get install python-gdown

**By pip**

.. code-block:: bash

  pip install gdown

