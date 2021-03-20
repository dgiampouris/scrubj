# Scrubj
## A collection of scripts that utlimately import C functions to Neo4j

This repository is collection of scripts, that import every function in
C code as a node in a graph database, in this case Neo4j.
Every function call is represented as an edge. Once the compilation process is
finished, there should be a represantation of the call graph in the database.

The general purpose is to be able to query the database and possibly discover patterns
in the codebase and attain a greater understanding of it.

## How to Use

Dependencies:

[gcc-python-plugin](https://gcc-python-plugin.readthedocs.io/en/latest/basics.html#building-the-plugin-from-source)
(select the branch that is correct for the gcc version you have installed).
[pyzmq](http://zeromq.org/bindings:python)

Make sure that you build the gcc python plugin correctly and 
`export LD_LIBRARY_PATH=(yourpath)/gcc-python-plugin/gcc-c-api/`

Also check out the usage of the [gcc-python-plugin](https://gcc-python-plugin.readthedocs.io/en/latest/basics.html#basic-usage-of-the-plugin).

You'll also need a Neo4j database instance and the abillity to connect to it via
a bolt connection.

The first step is to create a directory named feeds in `/tmp` (e.g. `mkdir /tmp/feeds`).
Then execute `receiver.py`. The receiver will standby until there is a gcc compilation.
Use gcc as you would normally, just add the parameters indicated in the
gcc-python-plugin basic usage documentation.

**This project works only with gcc.**
