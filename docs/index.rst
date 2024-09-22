.. toctree::
   :hidden:

   Intro <self>
   api
   GitHub project page <https://github.com/wagnerflo/noblklog>

=================================
Non-blocking handlers for logging
=================================

In contrast to existing frameworks for logging from within Python’s
:mod:`asyncio`, noblklog works hard to provide a implementation that
just works as is. It will not require to learn and use a different
logging API with caveats different from the standard library. The
handlers it provides can be used with any application built on
:mod:`logging` by simply changing the logging configuration.


How to install?
---------------

There`s absoluelty no magic here. Just the usual. No compiling required
either::

  $ pip install noblklog


How to use?
-----------

Even less magic (wait for it: there’ll be some later on) and answering
this question depends on your enviroment and preferences.

For taking it for a quick ride while testing or in scripts the commonly
used :func:`~logging.basicConfig` is your best bet:

.. literalinclude:: ../examples/simple.py
   :language: python

If you build a more sophisticated application it is quite
propable that at one point you might provide configurable logging using
:func:`~logging.config.fileConfig` or
:func:`~logging.config.dictConfig`. Maybe like this.

.. literalinclude:: ../examples/fileConfig.py
   :language: python

And this.

.. literalinclude:: ../examples/fileConfig.ini
   :language: ini


Where else can I send log messages?
-----------------------------------

See the :doc:`/api` part of the documentation.


Anything to look out for?
-------------------------

Yes. Don't log too much. To preserve order of log messages while still
being able to keep it’s promise of being non-blocking, **noblklog**
will sometimes have to queue messages. This is only necessary if the
handler’s destination file descriptor (temporarily) won’t accept writes.
Log too many and/or too big messages and this will happen. If you just
keep on logging the message queue will eat your memory.

In practice for normal sized software components with run of the mill
logging behaviour this is not a problem that will surface.
