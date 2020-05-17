# AWFUL &#128534;: Arguably Worst F\*cked-Up Language #

> &copy; 2019-2020 Arne Bachmann.

[![Build status](https://ci.appveyor.com/api/projects/status/hal78qt4cbkis9hh?svg=true)](https://ci.appveyor.com/project/ArneBachmann/awful)

This project implements an interpreter for the stack-based programming language *AWFUL*, written in Python.
AWFUL takes inspiration from many programming language designs and concepts, but is not really informed by them and combines them in the most awful way (e.g. use of terms may differ from existing languages).

The result is a fun little programming language and an usable interpreter that allows to write stack-based programs with a reduced set of keywords and language concepts.
Here is an example with extensive stack operations:

```
# Fibonacci implementation

include stack


## Compute the Fibonacci numbers iteratively
def fib  1
  dup is-neg if (
    error "fib requires a positive interger"
  )
  dup 1 le if break       # for 0 and 1, just return this number

  def fib'  3             # q p n
    dup 1 le              # q p n n<=1
      if break pop2       # q  -> exit
    3tor over             # n q p q
    +                     # n q p+q
    swapover              # p+q q n
    1 -                   # p+q q n-1
    fib'                  # tail recursion
  end  1

  1 0                     # n 1 0
  rot3                    # 1 0 n  rearrange the function arguments
  fib'                    # start the tail-recursive loop
end  1


## Test cases
assert -1 "ERROR" from -1 fib end
assert 0          from 0 fib end
assert 1          from 1 fib end
assert 8          from 6 fib end
assert 6765       from 20 fib end
```

AWFUL's features include:

- bootstrap language definition (parts of the language like `for` loops are built up from a few primitives like `pop`)
- tail recursion optimization (no callstack limitation due to recursion)
- hierarchical type system (internal data type representations are built on top of each other)
- local namespaces
- nested variable structures (`a`, `a.b`)
- built-in testing capabilities via `assert` statement
- stack safety checks
- function references and variables `&`
- extensive internal state machine logging `--debug`, `--items`, `--stats`, `debug on/off/this/assert`
- nested `include`
- source files are valid Markdown documents
- general appearance and terminology inspired by Python
- there are no lexical scopes (all included code lines are interpreted as if they were one big file)


## Running the interpreter

> `awful arguments-and-options`

```
AWFUL V0.5  (C) 2019-2020 Arne Bachmann

python[3] awfl.py [-O] [file1.awfl [file2.awfl [...]]] [--options]

-O              Disable all runtime checks
--calls         Display call hierarchy
--debug         Show parser info and enable live debugger
--decimals <n>  Set decimal computation precision to n digits (default: 1000)
--help          Show this interpreter options
--interactive   In case of test case failure, drop into a python debug shell
--names         Display all words in all namespaces
--optimize      Remove most comments and assert statements from runtime
--repl          Start interactive AWFUL shell after processing given files
--run "<items>" Run given AWFUL commands and quit
--stats         Show interpreter run statistics before interpreter shutdown
--tokens        Display tokens at parsetime
--warn          Show runtime warnings to help finding code problems
--test          Run test cases

Debug command options: on, off, this
```


## Definitions
- *token*: a string of characters extracted from the source file, separated by whitespace from adjacent tokens (exceptions: quoted string parsing and comments, which after parsing constitute one token even with spaces included)
- *symbol*: a token that is used to specify a data structure key.
            Symbols are usually represented starting with a colon, e.g. `:num`
- *variable*: a data structure stored in a namespace under a certain key.
             Invoking the key puts (a copy of) the variable's contents on the stack; function variables put a function reference on the stack)
- *data structure*: the internal representation of any data, implemented as Python dictionaries (!)
- *TOS*: top of stack (top-most element)
- *NOS*: next of stack (second element from top)


## Implementation details
- token parsing errors (syntax, grammar) and runtime violations (function stack invariants and type checks) are issued by two separate exceptions
- the internal data representation for *all* AWFUL data types are, for symmetry's sake, *always* dictionaries with keys as static Python strings (symbols from the token stream, or stringified integers), and mapped values as integers.
    For built-in types and standard library types, the 'type' points to a numeric type identifier
  - `nil` is a singleton data type with no other map keys except `type` being set to `0`
  - lists are implemented as Python `dict`s with the key being the list index 0..n-1
    - strings are implemented as lists of charset codepoints
      - numbers are implemented as serialized strings from Python data types `int` \< `fraction` \< `decimal`
        - Boolean values with the symbols `True` and `False` are implemented having a numeric value of -1 and 0, respecitvely
- since many interpreter operations on the stack's data structure are in-place, the runtime usually makes deep copies of data to avoid reference problems


## Namespaces
- each namespace (or vocabulary in Forth lingo) constitutes a set of local words that can be looked up (a word points to either a function or a data structure)
- nested namespaces are implemented as a stack of Python maps that can be accessed from top (local) to bottom (global)
- each function call creates a fresh local namespace at runtime; the outer namespaces can explicitly be referenced by dot prefixes (one dot per parent) - this usually requires the user to know how many parent hops are needed to modify a variable in the outer scopes and makes composition hard
  - when *not* using the dot notation, symbols are automatically looked up in parent namespaces up to the global one, otherwise a runtime exception interrupts the program
- redefine a function by using a `dyndef` in a deeper namespace


## Stack
- there is one global stack that facilitates data transfer between all consecutive operations
- basic stack operations supported in AWFUL:
  - `dup`: duplicate (deep-copy) TOS
  - `pop`: remove TOS
  - *`n`* `nib`: remove n-th topmost element and push it onto TOS (0 = keep TOS, 1 = swap with TOS, 2 = rotate 3 elements)
  - *`n`* `bin`: remove TOS and insert it down n positions (0 = keep at TOS, 1 = swap with NOS, 2 = reverse rotate 3 elements)


## Variables
- variable names are stored as words in the current namespace and may optionally contain nested sub-entries via dot notation
- variable definition: *`value`* `as name[.sub1[.sub2[...]]]>`  store value under `name` in current namespace
- variable update:     *`value`* `up name`  update value of `name` in current namespace
- variable destruction:          `rm name`. Be careful:  removes variable from the current runtime namespace, not necessarily the one the variable was defined in!


## Data structures
- to manipulate data in more complex data types, the following operations must be used:
  - *`data :symbol`*              `pull`  extract the substructure `symbol` (or an integer index) from the datum and pushes on top of the stack
  - *`data substructure :symbol`* `push`   add or update the substructure in the datum, consuming it from the stack
  - *`data substructure :symbol`* `pushi`  add or update a direct integer value under the symbol key, consuming it from the stack (this is used to manipulate code points or internal metadata like `:type` and `:num` directly)


## Functions
- function invocation: *`arguments`* `name`  call a function that consumes zero or more input arguments from the stack and puts zero or more output values onto the stack
- function reference creation: `&name`  puts a reference to the function on the stack
- function reference invocation: *`arguments reference`* `apply`  call a function from a function reference in TOS
- global function definition: `def name n-input-args body end m-output-args`

  - `inputs` and `outputs` are integers that define the expected number of elements on the stack before and after the function call
  - the function body will be evaluated on each call, including potentially contained function definitions and asserts
- local function definition `dyndef name n-input-args body end m-output-args`, similar to a global function definition, but is precompiled and only available in the inner scope. Allows redefining already occupied function names


## Language design
- Originally nested variables, including numeric indexes, could be accessed directly via dot notation.
  This, however, required the AWFUL code to compute the variable sub-path keys via concatentation.
  Since concatenation was to be programmed in AWFUL itself, there was a deadlock situation between interpreter and language bootstrapping.

  The solution to that problem was the introduction of the `push[i]` and `pull` commands that combine or extract sub-structures.
  This way we can still implement the list and string concatenation functions in AWFUL and retain the sub-structures feature in the language with very little specialized code.


## Coding guidelines
- When mixing stack with reference variables, prefer variables retrieval over stack duplication
- Loop functions usually have the form of
    1. variable processing (from stack)
    2. step function definition
    3. loop invocation
    4. postprocessing
- Naming recommendations
  - Name variables using the function name as a prefix (e.g. `for` implememtation has an internal variable `for-step`).
    This makes it easier to detect and avoid naming clashes
  - Use the single quote suffix for single naming clash avoidance


## Standard library dependency hierarchy
- standard
  - basicmaths
  - basics
  - files
  - lists
  - loops
  - maps
  - selftests
  - sets
  - stack
  - types
- maths
  - basicmaths
  - lists
  - stack
  - strings
  - types
- io
  - console
  - streams
  - strings

Please note that many library implementations favor the use of other existing library functions over careful algorithm design, often leading to very disadvantageous runtime behavior of `O(n^^3)` or worse.


## Debugging
- Insert print statements like `stdout "Bla" printfn`
- Insert `debug this` for stack prints
- Use `debug on` and `debug off` to enable detailed output for a passage of code
- Enable loggers via `--warn` and `--debug`
- Use `--calls`, `--names`, `--tokens`
- Use `--fifo` for a number of last tokens and stacks
- Use `--interactive` to drop into the Python debugger


## To do
- allow empty function bodies?
- document all keywords
- option to run assert statements only once (not on every call?)
  - remove assert from token string after execution?
  - add test vs. assert
- add exception catching: try block catch block end?
- optimization: refactor literal lists and functions into one big static table
  - function invariant checking should be done in the interpreter, not in Python functions
- add evaluated lists (?)
- improve error reporting - often you only get obscure Python exceptions without a more specific AWFUL hint
  - leave file and line number in items
- add polymorphism?
- remove all EOLs from item string?
- allow more special character escaping (\n\r\t \0\xXX\uXXXX\UXXXXXXXX) in literal strings
- use colored syntax in REPL
  - implement full grammar using some kind of parser library (?)
- implement graphics processing, implement e.g. game of life
- add multi threading capabilities?
- interpret `alias` only once


## Defined types

### Interpreter type internals
- -2: open file handle
- -1: codepoint
- 0: `nil`
- 1: bool
- 2: number
- 3: string
- 4: list
- 5: function (reference)

### Standard library
- 6: maps
- 7: sets


## Performance
The interpreter's performance is - as expected - not just horrible, but really awful.
For the Fibonacci code, a slowdown factor of roughly 1000 compared to Python is observed.
Maps are implemented as lists implemented as nested dictionaries...

You can skip running all self-tests, pre- and post-conditions and invariant checking by providing `-O` to the Python interpreter (this disables all Python asserts).
Using the command line option `--optimize` will skip all AWFUL `assert` statements as well.

```
> time python3 awfl.py fibonacci.awfl
real  0m39.041s
user  0m39.011s
sys   0m0.024s

> time python3 -OO awfl.py fibonacci.awfl
real  0m37.534s
user  0m37.516s
sys   0m0.012s

> time pypy3 awfl.py fibonacci.awfl
real  0m12.191s
user  0m12.130s
sys   0m0.040s

> time python3 fibonacci.py
real  0m0.043s
user  0m0.035s
sys   0m0.008s

> time pypy3 fibonacci.py
real  0m0.083s
user  0m0.067s
sys   0m0.016s
```
