# AWFUL &#128534;: Arguably Worst F\*cked-Up Language #

> &copy; 2019 Arne Bachmann.

This project implements an interpreter for the stack-based programming language *AWFUL*, written in Python.
AWFUL takes inspiration from many programming language designs and concepts, and combines them in the most awful way.
The result is a fun programming language runtime that allows to write stack-based programs with a reduced set of keywords and language concepts. Here is an example:

```
# Iterative Fibonacci computation #

include basics
include stack


def fib  1              # expects one (input argument) value on the stack
  dup neg
  if error "fib requires a positive interger"
  dup 1 le if break     # for 0 and 1, just return the number

  def fib'  3           # q p n     inner function definition
    dup 1 le            # q p n n<=1
    if break pop pop    # q         stack cleanup
    3tor over           # n q p q   3tor = reverse of rot3
    +                   # n q p+q
    swap                # n p+q q
    rot3                # p+q q n
    1 -                 # p+q q n-1
    fib'
  end  1

  1 0                   # n 1 0     here starts the regular function
  rot3                  # 1 0 n
  fib'
end  1                  # expects one (output return) value on the stack
```

AWFUL's features include:
- bootstrap language definition (parts of the language are implemented from very few primitives, e.g. `for`, `pop`)
- tail recursion optimization (no callstack limitation due to recursion)
- hierarchical type system
- local namespaces
- nested variable structures
- built-in testing capabilities (assert statement)
- function references
- extensive internal state machine logging
- nested include files
- source files are markdown-compatible  TODO remove \`\`\`
- general appearance similar to Python code


## Definitions ##
- *token*: a string of characters extracted from the source file, separated by space from the other tokens (exceptions: quoted string parsing and comments, which constitute one token even with spaces included)
- *symbol*: a token that is used to specify a data structure key. always starts with a colon, e.g. `:num`
- *variable*: a data structure stored in a namespace under a certain key. Invoking the key puts the variable's contents on the stack
- *data structure*: the internal representation of any data, implemented as Python dictionaries
- *TOS*: top of stack (topmost element)
- *NOS*: next of stack (second most element)


## Implementation details ##
- token parsing errors (syntax, grammar) and runtime violations (function stack invariants and type checks) are handled by two separate exceptions
- the internal data representation for all AWFUL data types are always dictionaries with keys as static Python strings (symbols from the token stream or integers), and values as integers
- lists are implemented as maps with the key being the list index 0..n-1
- strings are implemented as lists of charset codepoints
- numbers are implemented as serialized strings from Python data types int \< fraction \< decimal
- Boolean truth values with the symbols `True` and `False` are implemented as a default variable of type boolean with a value of -1 and 0, respecitvely
- `nil` is a singleton data type


## Namespaces ##
- each namespace constitutes a set of local words that can be looked up (words point to either a function or a data structure)
- nested namespaces are implemented as a stack of Python maps that can be accessed from top (local) to bottom (global)
- each function call creates a fresh local namespace during runtime; the outer namespaces can explicitly be referenced by dot prefixes (one dot per parent)
- when not using the dot notation, symbols are automatically looked up in parent namespaces up to the global one, otherwise a runtime exception interrupts the program


## Stack ##
- there is one global stack that facilitates data transfer between all consecutive operations
- Basic stack operations supported in AWFUL:
  - `dup`: duplicates (copies) TOS
  - `pop`: removes TOS
  - `*n* nib`: remove n-th topmost element and push it onto TOS (0 = keep TOS, 1 = swap with TOS, 2 = rotate 3 elements)
  - `*n* bin`: remove TOS and insert it down n positions (0 = keep at TOS, 1 = swap with NOS, 2 = reverse rotate 3 elements)


## Variables ##
- variable names are stored as words in the current namespace and may optionally contain nested sub-entries via dot notation
- variable definition: *value* as `name[.sub1[.sub2[...]]]>`  stores value under `name` in current namespace
- variable update: *value* `up name`  updates value of `name` in current namespace
- variable destruction: `rm name`


## Data structures ##
- to manipulate data in more complex data types, the following operations must be used:
  - *data :symbol* `pull`  extracts the substructure `symbol` (or an integer index) from the datum and pushes on top of the stack
  - *data substructure :symbol* `push`  adds or updates the substructure in the datum, consuming it from the stack
  - *data substructure :symbol* `pushi`  adds or updates a direct integer value under the symbol key, consuming it from the stack


## Functions ##
- function invocation: *arguments* `name`  calls a function that consumes zero or more input arguments from the stack and puts zero or more output values onto the stack
- function reference creation: `&name`  puts a reference to the function on the stack
- function reference invocation: *arguments reference* `apply`  calls a function from a function reference in TOS
- function definition: `def name n-input-args body end m-output-args`

  - `inputs` and `outputs` are integers that define the expected number of elements on the stack before and after the function call
  - the function body will be evaluated on each call, including potentially contained function definitions and asserts


## Language design ##
- Originally nested variables could be accessed directly via dot notation.
  This, however, required the AWFUL code to compute the variable sub-paths via concatentation.
  Since concatenation was to be programmed in AWFUL itself, there was a deadlock between interpreter and language bootstrapping.

  The solution to that problem was the introduction of the `push` and `pull` commands that combine or extract sub-structures.
  This way we can still implement the list and string concatenation functions in AWFUL and retain the sub-structures feature in the language with very little specialized code.


## Coding guidelines ##
- When mixing stack with reference variables, prefer variables retrieval over stack duplication
- Loop functions usually have the form of
    1. variable processing (from stack)
    2. step function definition
    3. loop invocation
    4. postprocessing


## Standard library dependency hierarchy ##
- loops
  - stack
    - basics
      - selftests
- maths
  - stack
    - basics
      - selftests
- strings
  - lists
    - loops
      - stack
        - basics
          - selftests
  - loops
    - stack
      - basics
        - selftests
- types
  - stack
    - basics
      - selftests


## To do ##
- automatic coercion rules and methods
- let up :name automatically traverse namespaces until found, or raise Exception
- Refactor literal lists and functions into one static table
  - function invariant checking should be done in the interpreter, not in Python functions
- Add evaluated lists (?)
- Add dynamic functions (?)
  - make distinction between dynamic and static functions/aliases?
- make decimal precision configurable in user code
- Improve error reporting - often you only get obscure Python exceptions without a more specific AWFUL hint
  - leave file and line number in items
- Add polymorphism?
- remove all EOLs from item string?
- profile performance
- allow more special character escaping (\n\r\t \0\xXX\uXXXX\UXXXXXXXX) in literal strings
- use colored syntax in REPL
  - implement full grammar using some kind of parser library (?)
- implement file handling and input/output processing
- implement graphics processing, implement game of life
- add multi threading?


## Performance ##
The interpreter's performance is - as expected - not just horrible, but really awful.
For the Fibonacci code, a slowdown factor of 1000 compared to Python is observed.

You can skip running all self-tests, pre- and post-conditions and invariant checking by providing `-O` to the Python interpreter (this disables all Python asserts). Using the command line option `--optimize` will really skip the AWFUL assert statements alltogether.

```
> time python3 awfl.py fibonacci.awfl
real 0m38.142s
user  0m38.125s
sys 0m0.017s

> time python3 -O fibonacci.py
real  0m35.259s
user  0m35.246s
sys 0m0.012s

> time pypy3 awfl.py fibonacci.awfl
real  0m12.626s
user  0m12.571s
sys 0m0.052s
```
