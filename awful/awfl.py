''' AWFUL: Arguably's Worst F*cked-Up Language.
    Copyright (c) 2020 Arne Bachmann.
'''

import copy, decimal, doctest, fractions, os, sys, time
assert sys.version_info >= (3, 5)
from functools import reduce


VERSION = "0.5.1"

# Reserved language words and operators
EOL, TAIL_RECURSION = '__EOL__', '__TAILR__'
NIL, UNKNOWN = 'nil', '?'
SYMBOLS = COMMENT, SYMBOL, QUOTE, DOT, REF = '#', ':', '"', '.', '&'
ESCAPE, SPACE = '\\"', ' '
NUMERICS = PLUS, MINUS, TIMES, DIVMOD = '+', '-', '*', '//'
BITWISE = BAND, BOR, BXOR = 'band', 'bor', 'bxor'
GROUPING = GROUP, ENDGROUP = '(', ')'
LISTS = NEWLIST, DYNLIST, ENDLIST = '[', '![', ']'
TRUTH = TRUE, FALSE = 'True', 'False'
STACKOPS = NIB, BIN, POP, DUP = 'nib', 'bin', 'pop', 'dup'  # basic stack operations
FUNCTIONS = ALIAS, APPLY, DEF, DYNDEF, END = 'alias', 'apply', 'def', 'dyndef', 'end'
CONDITIONAL = NOT, IF, EQ = 'not', 'if', 'eq'
ORDERED = LE, GE = 'le', 'ge'
VARIABLES = AS, UP, RM = 'as', 'up', 'rm'
STRUCTURES = PULL, PUSH, PUSHI = 'pull', 'push', 'pushi'
FILES = OPEN, CREATE, CLOSE, READ, WRITE = 'open', 'create', 'close', 'read', 'write'
STREAMS = STDIN, STDOUT, STDERR, SYSTEM = '_stdin', '_stdout', '_stderr', 'system'
INTERRUPTS = BREAK, ERROR = 'break', 'error'
TESTING = ASSERT, FROM = 'assert', 'from'
INTERACTIVE = DEBUG, IGNORE, ON, OFF, THIS = 'debug', 'ignore', 'on', 'off', 'this'
SOURCE = LIBS, INCLUDE, WORDS = 'libs', 'include', 'words'
RESERVED_KEYWORDS = set(reduce(lambda a, b: a + (list(b) if isinstance(b, tuple) else [b]), (NIL, SYMBOLS, NUMERICS, GROUPING, LISTS, TRUTH,
    STACKOPS, FUNCTIONS, CONDITIONAL, ORDERED, VARIABLES, STRUCTURES, FILES, STREAMS, INTERRUPTS, TESTING, INTERACTIVE, SOURCE), []))
DEFS = {ALIAS: END, ASSERT: FROM, DEF: END, DYNDEF: END, FROM: END, GROUP: ENDGROUP, NEWLIST: ENDLIST, ERROR: EOL, BREAK: EOL}  # tokens that open and close a sublist in the token string
NAMEDEFS = {k: v for k, v in DEFS.items() if k in (ALIAS, DEF, DYNDEF)}  # the ones with a name following

# Further constants
INDENT_N = 2  # spaces per indentation step
INDENT = SPACE * INDENT_N
TYPE, NUM, NONE = 'type', 'num', None  # reserved fields in internal data representation
TYPES = FILE, CODE, NILT, BOOL, NUMBER, STRING, LIST, FUNC = -2, -1, 0, 1, 2, 3, 4, 5  # of internal presentation dict[TYPE]
# type identifiers used in the standard library: 6 = maps, 7 = sets
SEP = " " if "--compact" in sys.argv else "\n"


class ParsingError(Exception): pass
class RuntimeViolation(Exception): pass

class Queue(list):
  def __init__(_, size = 15): list.__init__(_); _.size = size
  def append(_, elem):
    list.append(_, elem)
    if len(_) > _.size: _.pop(0)


class TokenIter(object):
  ''' Implements an iterator that allows prepending tokens into the stream. '''
  def __init__(_, tokens): _.alias, _.tokens = [], iter(tokens)
  def __next__(_): return _.alias.pop(0) if _.alias else next(_.tokens)
  def insertAlias(_, alias): _.alias = alias + _.alias  # prepend tokens


# Interactive input for stdin reading
try:  # from https://gist.github.com/payne92/11090057
  import msvcrt
  getch = msvcrt.getwch
except:  # Linux
  import termios, tty
  def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try: tty.setraw(sys.stdin.fileno()); ch = sys.stdin.read(1)
    finally: termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def formatCodeBlock(lizt, indent = 0):
  ''' Printable representation of condensed parsed items.
  >>> print(formatCodeBlock(['[', ['1', '2', '3']]))  # doctest: +ELLIPSIS
  [ 1 2 3 ]...
  '''
  i, n, s = 0, len(lizt), []
  while i < n:
    elem = lizt[i]; i += 1
    if elem == EOL: s.append("\n" + INDENT * indent)
    if elem in DEFS or elem[0] in DEFS:
      s.append(elem + " ")
      i += 1; s.extend(formatCodeBlock(lizt[i - 1], indent + 1))
      s.append(DEFS[elem] + " ")
      continue
    s.append(elem + " ")
  return s if indent else "".join(s)


def parseNumber(s):
  ''' Converts a literal string token into a number.
      Allowed formats: 1 -1. .1 0.1 -1.2 1e2 2/-3 (integers, fractions, decimals)
  >>> repr(parseNumber("1"))
  '1'
  >>> repr(parseNumber("1/5"))
  'Fraction(1, 5)'
  >>> repr(parseNumber("1.5"))
  'Fraction(3, 2)'
  '''
  assert isinstance(s, str)
  try: value = int(s)  # attempt to treat most numbers as integers
  except (TypeError, ValueError):
    try: value = fractions.Fraction(s)  # try to treat as integer fraction
    except (TypeError, ValueError):
      try: value = decimal.Decimal(s)  # last resort: arbitrary length decimal
      except Exception as E: raise ParsingError("cannot parse number %r" % s)  # HINT: this ParsingError is also issued at runtime!
  return value


## Create internal representation from Python types
def makeList(lizt):
  ''' Create the internal representation for ordered entries.
      Expects the input to be a list of integers and nested lists of the same format.
      Dicts are recognized as already converted contents (e.g. from fromLiteral()).

  >>> orderedDictRepresentation(makeList([1, 3, 5]))
  "[('0', 1), ('1', 3), ('2', 5), ('num', 3), ('type', 4)]"
  >>> orderedDictRepresentation(makeList([1, [], [3, 5]]))
  "[('0', 1), ('1', [('num', 0), ('type', 4)]), ('2', [('0', 3), ('1', 5), ('num', 2), ('type', 4)]), ('num', 3), ('type', 4)]"
  '''
  assert isinstance(lizt, list), "makeList requires a list argument, but got %r" % lizt
  assert all([isinstance(_, (int, dict, list)) for _ in lizt]), "makeList requires a list of integers or nested lists, but got %r" % lizt
  dikt = {NUM: len(lizt), TYPE: LIST}
  for i in range(len(lizt)): dikt[str(i)] = lizt[i] if not isinstance(lizt[i], list) else makeList(lizt[i])
  return dikt

def makeString(string):
  ''' Convert a literal string into internal list/map representation.

  >>> orderedDictRepresentation(makeString("abc"))
  "[('0', 97), ('1', 98), ('2', 99), ('num', 3), ('type', 3)]"
  '''
  assert isinstance(string, str)
  dikt = makeList([ord(string[i]) for i in range(len(string))])
  dikt[TYPE] = STRING
  return dikt

def makeNumber(n):
  ''' Convert number to internal representation.
  >>> orderedDictRepresentation(makeNumber(fractions.Fraction("45/23")))
  "[('0', 52), ('1', 53), ('2', 47), ('3', 50), ('4', 51), ('num', 5), ('type', 2)]"
  '''
  if not isinstance(n, (int, fractions.Fraction, decimal.Decimal)): raise RuntimeViolation("Wrong number type %s: %r" % (type(n), n))
  dikt = makeString(str(n))
  dikt[TYPE] = NUMBER
  return dikt

def makeReference(name):
  ''' Create a function reference entry.
  >>> orderedDictRepresentation(makeReference("my"))
  "[('0', 109), ('1', 121), ('num', 2), ('type', 5)]"
  '''
  assert isinstance(name, str)
  dikt = makeString(name)
  dikt[TYPE] = FUNC
  return dikt

def makeBool(b):
  ''' Create a boolean entry. '''
  return {TYPE: BOOL, '0': -1 if b else 0}

def makeFile(file, read):
  ''' Create a open stream.
  >>> print(sys.stderr is makeFile("_stderr", False)[NONE])
  True
  >>> fd = makeFile(os.path.dirname(os.path.abspath(__file__)) + os.sep + "awfl.py", read = True); print(fd[NONE].name.endswith("awfl.py"))
  True
  '''
  return {'type': FILE, 'read': read, NONE: {STDIN: lambda: sys.stdin, STDOUT: lambda: sys.stdout, STDERR: lambda: sys.stderr}.get(file, lambda: open(file, 'rb' if read else 'wb'))()}

## Get data back from internal representation
def getType(dikt):
  ''' Determine type of internal representation.

  >>> getType({'type': 0})  # nil
  0
  >>> getType({'type': 1, '0': -1})  # a bool
  1
  >>> getBool({'type': 1, '0': -1})
  True
  >>> getBool({'type': 1, '0': 0})
  False
  >>> getType({'type': 2, 'num': 2, '0': 49, '1': 50})  # a number
  2
  >>> getNumber({'type': 2, 'num': 2, '0': 49, '1': 50})
  12
  >>> getType({'type': 3, 'num': 1, '0': 55})  # a string
  3
  >>> getString({'type': 3, 'num': 1, '0': 55})
  '7'
  >>> getType({'type': 4, 'num': 0})  # a list
  4
  >>> getList({'type': 4, 'num': 0})
  []
  >>> getType({'type': 5, 'num': 1, '0': 55})  # a function reference
  5
  '''
  if isinstance(dikt, list): return LIST
  if isinstance(dikt, int):  return CODE
  assert isinstance(dikt, dict), "getList with data type %s" % type(dikt)
  assert TYPE in dikt
  assert dikt[TYPE] in TYPES
  return dikt[TYPE]

def getList(dikt):
  assert getType(dikt) == LIST
  assert NUM in dikt
  return [fromValue(dikt[str(_)]) for _ in range(dikt[NUM])]

def getString(dikt, allowed_types = (STRING,)):
  ''' Convert internal list/map representation back into a string.
  >>> print(getString({'type': 3, 'num': 3, "0": 97, "1": 98, "2": 99}))
  abc
  '''
  assert getType(dikt) in allowed_types
  #assert all([isinstance(dikt[str(i)], int) for i in range(int(dikt[NUM]))]), dikt  # strings should not be nested - but could be if constructed from list-concat of code point integers
  return "".join([chr(getNumber(dikt[str(i)]) if isinstance(dikt[str(i)], dict) else dikt[str(i)]) for i in range(int(dikt[NUM]))])  # TODO when is char codepoint ever encoded as a dict?

def getNumber(dikt):
  ''' Convert internal representation back into a number.
  >>> print(getNumber({'type': 2, 'num': 4, "0": 49, "1": 50, "2": 47, "3": 53}))  # 12/5
  12/5
  '''
  return parseNumber(getString(dikt, allowed_types = (NUMBER,)))

def getBool(dikt):
  ''' Convert internal list/map representation into a bool.

  >>> print(getBool({'type': 1, '0': 234}))
  True
  >>> print(getBool({'type': 1, '0': 0}))
  False
  '''
  assert getType(dikt) == BOOL
  assert '0' in dikt
  return False if dikt['0'] == 0 else True


TYPE2FUNC = {NILT: lambda _: NONE, BOOL: getBool, CODE: lambda i: i, NUMBER: getNumber, STRING: getString, LIST: getList}  # getter functions by data type
TYPE2NAME = {NILT: NIL, BOOL: 'boolean', CODE: 'code', NUMBER: 'number', STRING: 'string', LIST: 'list', FUNC: 'function'}  # type names by data type
def fromValue(value): tipe = getType(value); return repr(value) if tipe not in TYPE2FUNC else TYPE2FUNC[tipe](value)


## Functions to output the interpreter state
def orderedDictRepresentation(simple_or_dikt, convert = str):
  ''' Reliable (ordered) representation for test cases and comparison operators.
  >>> orderedDictRepresentation({"a": 1, '1': 97, "_": {'3': 3}})
  "[('1', 97), ('_', [('3', 3)]), ('a', 1)]"
  '''
  return convert([(k, orderedDictRepresentation(v, convert = lambda a: a)) for k, v in sorted(simple_or_dikt.items())] if isinstance(simple_or_dikt, dict) else simple_or_dikt)

def internalAsString(e, indent = 0, prefix = "", sep = "\n"):
  ''' Create printable representation of a data type.
      Each recursion takes care of its own indentation.

      e: internal representation or codepoint
      indent: indentation level
      prefix: for nested variables, this is the full path. in this case, the indentation is skipped (right-hand side of ->)
  >>> print(internalAsString({'a': 1, 'b': {'c': 2, 'd': 3, 'e': {'f': -1, 'type': 1, '0': 0}, 'type': 7}, 'type': 0}))
  nil {
    a -> 1
    b -> {
      c -> 2
      d -> 3
      e -> False { f -> -1 }
      type -> 7
    }
  }
  >>> print(internalAsString({'type': 4, 'num': 1, '0': {'type': 2, 'num': 1, '0': 49}}))
  [ 1 ]
  >>> print(internalAsString({'type': 4, 'num': 2, '0': {'type': 2, 'num': 1, '0': 49}, '1': {'type': 1, '0': 0}}))
  [
    1
    False
  ]
  >>> print(internalAsString({'type': 5, 'num': 1, '0': 97}))
  &a
  >>> print(internalAsString({'type': 3, 'num': 1, '0': 97}))
  :a
  '''
  i = INDENT * indent; j = i + INDENT; p = (i if not prefix else "")  # first and second level indentation
  assert isinstance(e, int) or (isinstance(e, dict) and TYPE in e), "wrong type %r" % e  # int and list = internal dict values
  if isinstance(e, int): return p + str(e)  # pure integer codes
  tipe = e[TYPE]
  if   tipe == NILT: value = p + NIL  # noqa: E271
  elif tipe == BOOL: value = p + str(getBool(e))
  elif tipe == FUNC: value = p + REF + getString(e, allowed_types = (FUNC, ))
  elif tipe == FILE: value = p + QUOTE + {sys.stdin: lambda: STDIN, sys.stdout: lambda: STDOUT, sys.stderr: lambda: STDERR}.get(e[NONE], lambda: e[NONE].name)() + QUOTE
  elif tipe in (NUMBER, STRING):
    assert NUM in e
    value = p + (str(getNumber(e)) if tipe == NUMBER else ((QUOTE + getString(e) + QUOTE) if e[NUM] > 1 and not (e[NUM] == 1 and e[0] == ord(' ')) else (SYMBOL + getString(e) if e[NUM] > 0 else QUOTE * 2)))
  else: value = ""
  try: keys = set(([TYPE, NONE] if TYPE in e and e[TYPE] in TYPES else []) + ([str(n) for n in range(e[NUM])] + ([NUM] if tipe in TYPES else []) if NUM in e else (['0'] if tipe == BOOL else [])))  # expected keys
  except TypeError as E: raise RuntimeViolation("did you use push instead of pushi? %r" % E)
  keys = set(e.keys()) - keys  # unexpected keys to display
  if tipe == LIST:  # list-like
    value += p + ("[" + sep if e[NUM] > 1 else "[ ")
    value += sep.join([internalAsString(e[str(n)], indent + 1 if sep != " " and e[NUM] > 1 else 0, sep = sep) if str(n) in e else ((j if e[NUM] > 1 else "") + '<undef>') for n in range(e[NUM])])
    value += (sep + i + "]") if e[NUM] > 1 else " ]"
  if keys:  # further sub-entries
    value += (" " if value != "" else "") + "{" + (sep if len(keys) > 1 else " ")  # opening brace
    value += sep.join("%s%s -> %s" % (j if len(keys) > 1 else "", key, internalAsString(e[key], indent + (1 if sep != " " else 0), prefix + DOT + key, sep = sep)) for key in sorted(keys))
    value += sep + "%s}" % i if len(keys) > 1 else " }"  # closing brace
  return value

def stackStr(stack, sep = "\n"):
  return (("<%s" % sep if len(stack) > 1 else "<") + sep.join([internalAsString(_, 0 if len(stack) == 1 else 1, sep = sep) for _ in stack]) + ("%s>" % sep if len(stack) > 1 else ">")) if len(stack) > 0 else "< >"

def _namespaceStr(namespace):
  return ",\n".join(["%s%s -> %s" % (2 * INDENT, k, REF + v.name if callable(v) else internalAsString(v, 1)) for k, v in sorted(namespace.items())])

def namespaceStr(namespaces):
  return "NAMES\n  [%s\n  ]" % "\n  ], [".join([("\n" if namespace else "") + _namespaceStr(namespace) for namespace in namespaces])  # last two depths


## Working with nested variables
def variableTraversal(inDict, key):
  ''' Traverse down a sub-variable path
      inDict: heap or parent variable
      key: full or remaining key
  >>> list(variableTraversal({'a': {'b': {'c': {'type': 0}}}}, 'a.b.c'))
  [({'a': {'b': {'c': {'type': 0}}}}, 'a'), ({'b': {'c': {'type': 0}}}, 'b'), ({'c': {'type': 0}}, 'c')]
  >>> list(variableTraversal({}, ''))
  []
  '''
  while DOT in key:
    i = key.index(DOT)  # from left
    prefix, remainder = key[:i], key[i + 1:]
    yield inDict, prefix
    inDict, key = inDict[prefix], remainder
  while key.endswith(DOT): key = key[:-1]  # remove trailing dots
  if key == '': return  # exit generator
  yield inDict, key

def storeVariable(inDict, key, value, update = False, original = None):
  ''' Store or update a potentially nested variable.
      inDict: namespace or variable with nested structures
      key: variable name or path
      value: data structure to store
      original: original path
  >>> ns = {}; storeVariable(ns, "a.b", {"type": 3, "0": 97, "num": 1}, original = "..a.b"); orderedDictRepresentation(ns)
  "[('a', [('b', [('0', 97), ('num', 1), ('type', 3)])])]"
  >>> storeVariable(ns, "a.b", {"type": 3, "0": 98, "num": 1}, update = True); orderedDictRepresentation(ns)
  "[('a', [('b', [('0', 98), ('num', 1), ('type', 3)])])]"
  >>> ns = {}; storeVariable(ns, "a.b", {"type": 3, "0": 97, "num": 1}, update = True); orderedDictRepresentation(ns)
  Traceback (most recent call last):
  ...
  RuntimeViolation: variable element 'a' not defined for 'a.b'
  '''
  assert isinstance(inDict, dict), "storeVariable not on namespace %r" % inDict
  assert isinstance(key,    str),  "storeVariable with wrong key type %r" % key
  assert isinstance(value,  dict), "storeVariable with wrong value type %r" % value
  if key in statics and not sut: raise RuntimeViolation("variable name %r already defined as static function" % key)  # redefinitions only allowed inside assert from block
  for inDict, prefix in variableTraversal(inDict, key):
    try:
      if prefix not in inDict:
        if update: raise RuntimeViolation("variable element %r not defined for %r" % (prefix, original if original else key))
        inDict[prefix] = {}
      elif not update and not sut: raise RuntimeViolation("variable element %r already defined for %r" % (prefix, original if original else key))
    except TypeError: import pdb; pdb.set_trace()
  if debug: print("%s %s -> %s" % ("VARUP" if update else "VARDF", key, internalAsString(value)))
  inDict[prefix] = value

#def updateVariable(inDict, key, value, original = None): storeVariable(inDict, key, value, update = True, original = original)

def getVariable(inDict, key, remove = False):
  ''' Return potentially nested variable.
  >>> getVariable({'a': {'b': {"type": 3, "0": 97, "num": 1}}}, 'a.b')
  {'type': 3, '0': 97, 'num': 1}
  >>> getVariable({'a': {'b': {"type": 0}}}, 'a.b')
  {'type': 0}
  '''
  assert isinstance(inDict, dict)
  assert isinstance(key, str)
  for inDict, prefix in variableTraversal(inDict, key):
    if prefix not in inDict: raise RuntimeViolation("variable element %r not found for %r" % (prefix, key))
  if remove:
    if debug: print("VARRM %s" % key)
    del inDict[prefix]
  else:  # get from dictionary/heap
    if isinstance(inDict[prefix], int): return makeNumber(inDict[prefix])
    if inDict[prefix].get(TYPE, -999) == FILE: return inDict[prefix]
    return copy.deepcopy(inDict[prefix])

def rmVariable(inDict, key):
  ''' Remove variable from heap or parent variable.
  >>> a = {'a': {'b': {'type':0 }, 'c': {'type': 1, '0': -1}}}
  >>> rmVariable(a, 'a.b')
  >>> a
  {'a': {'c': {'type': 1, '0': -1}}}
  '''
  getVariable(inDict, key, remove = True)

def compileFunction(op, name, inputs, block, outputs):
  ''' Compile an Awful function to a Python callable. '''
  if any([name in namespace for namespace in namespaces]): raise RuntimeViolation("%s %s already defined" % (op, name))
  while block and block[-1] is EOL or block[-1][0] == COMMENT: block.pop()  # remove unused tokens that prevent recognizing tail recursion
  if block and block[-1] == name: block[-1] = TAIL_RECURSION  # mark function as tail recursive

  def func(code, inputs, outputs):
    def inner(tokens, namespaces, stack):
      if debug: print("FUNCT %r" % name)
      if (debug or warn) and displayCallstack: print("CALLS %s.%s" % (".".join(callstack), name))
      global calls; calls += 1
      before = len(stack)
      if inputs > before: raise RuntimeViolation("function %s requires %d input arguments" % (name, inputs))
      try:
        namespaces.append({})  # create local namespace
        callstack.append(name)
        while True:  # potential tail-recursion loop
          error = interpret(TokenIter(code), namespaces, stack)  # run function code in its own namespace
          if error is TAIL_RECURSION:
            if debug: print("TAILR")
            continue  # run function again
          break
      except AssertionError as E: error = "%s: %r" % (".".join(callstack), str(E))  # affects unit test or pre-/post-conditions
      finally: namespaces.pop(); callstack.pop()
      if debug: print("ENDFN %r" % name) #  ; print("STACK " + stackStr(stack, SEP))
      if error: return error  # or break
      if outputs != UNKNOWN:  # check post-condition
        difference = len(stack) - (before - inputs + int(outputs))
        if difference != 0: raise RuntimeViolation("function %r stack size discrepancy %d" % (".".join(callstack + [name]), difference))
        return
    return inner  # applies function code body
  return func(block, inputs, outputs)



## The main interpreter functions
def interpret(tokens, namespaces, stack, breaker = None):
  ''' Execute the entire token stream, returning an optional error message. '''
  if not isinstance(tokens, TokenIter): raise RuntimeViolation("interpret encountered illegal token %r" % type(tokens))
  try:
    while True:
      retval = evaluate(tokens, namespaces, stack)  # runs one operation that potentially consumes more than one token
      if retval is BREAK: return breaker  # stop processing current block, and optionally return BREAK signal to outer caller (is None only outside a group)
      if retval:          return retval  # only cases are BREAK, TAIL_RECURSION and error message (or None for OK)
  except StopIteration: pass  # end of token stream reached

def evaluate(tokens, namespaces, stack):
  ''' Parses the next token(s) and interprets them.

      returns None for ordinary execution
      returns a string with an error message when encountering an unknown symbol
      returns BREAK to stop evaluating the current function (and not only current group)
      returns TAIL_RECURSION, passed on to caller by interpret() to let inner() know that the execution needs to be repeated/continued
  '''
  global counter, debug, statics, lastCalls, lastStacks
  counter += 1
  token = next(tokens)  # raises StopIteration exception when stream is depleted -> captured by interpret() above
  lastCalls.append(token); lastStacks.append(stack)
  assert isinstance(token, str)  # the tokenizer and parser ensure that each string has at least one character

  if token in (EOL, TAIL_RECURSION): return None if token is EOL else TAIL_RECURSION

  if displayNamespaces: print(namespaceStr(namespaces[-2:]))
  if debug:
    if debug == THIS: debug = False  # reset flag after printout
    if token[0] != COMMENT: print("STACK " + stackStr(stack, sep = SEP))
    print("TOKEN %s" % ({EOL: "EOL", TAIL_RECURSION: "TAILR"}.get(token, repr(token))))

  if token[0] == COMMENT: return  # comments are part of the token stream except in optimized mode
  if token == NIL: stack.append(fromLiteral(token)); return  # store nil singleton
  if token in TRUTH: stack.append(fromLiteral(token)); return  # boolean found
  if token.startswith(REF): stack.append(fromLiteral(token)); return  # put function reference on TOS (no namespace information contained!)
  if token.startswith(SYMBOL): stack.append(fromLiteral(token)); return  # put one-token symbol on the stack
  if token[0] == QUOTE: stack.append(fromLiteral(token)); return  # string found
  if token in aliases: tokens.insertAlias(aliases[token]); return  # alias found

  if token == WORDS:  # lists known words in REPL
    import termwidth, textwrap  # these imports are only required in the REPL when using 'words'
    for namespace in namespaces: print("\n".join(textwrap.wrap(", ".join(sorted(namespace)), termwidth.getTermWidth().columns - 1, initial_indent = "- "))); return

  if token == SYSTEM:  # "command" "input"|nil -> stdout, stderr, exitcode
    if len(stack) < 2 or getType(stack[-1]) not in (NILT, STRING) or getType(stack[-2]) != STRING: raise RuntimeViolation("%s requires command-string and input-string or nil on the stack %r" % (token, stack[-2:]))
    stream = stack.pop()
    stream = getString(stream) if getType(stream) == STRING else None  # nil
    command = getString(stack.pop())
    import subprocess
    process = subprocess.Popen(command, bufsize = -1, shell = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE, stdin = subprocess.PIPE, universal_newlines = True)
    so, se = process.communicate(stream)
    stack.append(makeString(so))
    stack.append(makeString(se))
    stack.append(makeNumber(process.returncode))
    return

  if token in (DUP, POP):
    if not stack: raise RuntimeViolation("%s requires one value on the stack" % token)
    if token == DUP: stack.append(copy.deepcopy(stack[-1]) if stack[-1].get(TYPE, -999) != -2 else stack[-1])
    if token == POP: stack.pop()
    return

  if token in (NIB, BIN):
    if not stack: raise RuntimeViolation("%s requires one integer argument on the stack" % token)
    value = stack.pop()
    if not getType(value) == NUMBER: raise RuntimeViolation("%s requires one integer argument on the stack" % token)
    n = int(getNumber(value))
    if n < 0: raise RuntimeViolation("%s argument must be a positive integer but is %d" % (token, n))
    if n > len(stack): raise RuntimeViolation("%s argument %d beyond stack size %s" % (token, n, stackStr(stack, sep = SEP)))
    if n > 0:
      if   token == NIB: stack.append(stack.pop(-n-1))
      elif token == BIN: stack.insert(-n, stack.pop())
    return

  if token in (BREAK, ERROR):  # common logic
    _next = next(tokens)  # optional clean-up operations on same line (or using a group definition in parentheses)
    if not isinstance(_next, list): raise RuntimeViolation("%s has body of wrong data type %r" % (token, _next))

    if token == BREAK:
      error = interpret(TokenIter(_next), namespaces, stack)  # cleanup operations
      return error if error else BREAK  # raised like an exception, but tells the calling function to jump to its end

    if token == ERROR:
      message = _next.pop(0)
      retval = interpret(TokenIter(_next), namespaces, stack)  # cleanup operations
      if debug: print("ERROR %s returned %r" % (message, retval))
      raise RuntimeViolation("%s %r " % (message, retval) + stackStr(stack, sep = SEP))  # notify interpret() about the error

  if token in VARIABLES:
    name = next(tokens)
    if debug and token != AS: print("NAME " + name)
    if token != RM and not stack: raise RuntimeViolation("%s without data on stack" % token)
    count, _name = -1, name  # remember original name for reporting
    name = name[1:] if name[0] == SYMBOL else name  # if written as symbol, ignore colon
    while name[0] == DOT: count -= 1; name = name[1:]  # find determine parent namespace
    if -count > len(namespaces): raise RuntimeViolation("too many parent indirections in variable name %r" % _name)
    if token == RM: rmVariable(namespaces[count], name); return
    value, prefix = stack.pop(), name if DOT not in name else name[:name.index(DOT)]  # get internal dict representation
    while token == UP and -count < len(namespaces) and (prefix not in namespaces[count] or callable(namespaces[count][prefix])): count -= 1  # find namespace with variable to update (ignoring functions of same name)
    if warn and token == AS:
      if any([name in namespace for namespace in namespaces[count-1:-len(namespaces):-1]]): print("WARN %s %s already exists in outer namespace" % (token, name))  # root-wise/deeper/global
      if any([name in namespace for namespace in namespaces[count+1:len(namespaces)]]):     print("WARN %s %s already exists in inner namespace" % (token, name))  # leaf-wise/higher/local
    storeVariable(namespaces[count], name, value, update = token == UP, original = _name)
    return

  if token in STRUCTURES:  # [item] structure symbol push[i]|pull
    if not stack: raise RuntimeViolation("%s requires one symbol or integer as key on the stack" % token)
    if len(stack) < (2 if token == PULL else 3): raise RuntimeViolation("%s requires %sstructure and key on the stack" % (token, "value, " if token == PUSH else ""))
    symbol = stack.pop(-1)
    if getType(symbol) == NUMBER: symbol = str(int(getNumber(symbol)))
    elif getType(symbol) == STRING: symbol = getString(symbol)
    else: raise RuntimeViolation("%s requires one symbol or integer as key on the stack but got %r" % (token, symbol))
    parent = stack[-1]  # we leave the existing structure on the stack
    path = [_ for _ in symbol.split(DOT) if _ != ""]  # safe split
    if token == PULL:
      while len(path) > 0:
        step = path.pop(0)
        if step in RESERVED_KEYWORDS: raise RuntimeViolation("%s using reserved symbol %r" % (token, symbol))
        if step not in parent: raise RuntimeViolation("%s key %s not contained in structure on stack %s" % (token, symbol, stackStr(stack, sep = " ")))
        parent = parent[step]
      stack.append(makeNumber(parent) if isinstance(parent, int) else parent)  # copy found datum to TOS
      return
    for step in path[:-1]:  # PUSH[I]: traverse until parent contains either the target key or a freshly created empty dict
      if step in parent: parent = parent[step]; continue
      parent[step] = {}  # create if not exists
    value = stack.pop(-2)  # consume data from stack
    parent[path[-1]] = int(getNumber(value)) if token == PUSHI else value  # integrate into data structure
    return

  if token in FILES:  # streams IO
    if len(stack) < (2 if token == WRITE else 1): raise RuntimeViolation("%s requires %d argument%s on the stack" % (token, 2 if token == WRITE else 1, "s" if token == WRITE else ""))
    argument = stack.pop(-1) if token in (OPEN, CREATE, CLOSE) else stack[-2 if token == WRITE else -1]  # consume (open) or leave (r/w)
    if getType(argument) != (STRING if token in (OPEN, CREATE) else FILE):
      raise RuntimeViolation("%s requires one %s on the stack but got %r" % (token, "string" if token in (OPEN, CREATE) else "stream", argument))
    if (token == CREATE and getString(argument) == "stdin") or (token == OPEN and getString(argument) in ("stdout", "stderr")):
      raise RuntimeViolation("%s on %s not allowed" % (token, argument))
    try:
      if token == OPEN: stack.append(makeFile(getString(argument), True)); stack.insert(-1, makeBool(True)); return  # success
      elif token == CREATE: stack.append(makeFile(getString(argument), False)); stack.insert(-1, makeBool(True)); return
      elif token == CLOSE and argument[None] not in (sys.stdin, sys.stdout, sys.stderr): argument[None].close(); return
    except: stack.extend([makeBool(False), {TYPE: NILT}]); return  # error
    if token == READ:
      value = getch() if argument[None] == sys.stdin else argument[None].read(1)
      stack.append(makeNumber(ord(value)) if value not in ('', b'') else {TYPE: NILT})
      return
    value = stack.pop(-1)  # get value for WRITE
    if getType(value) not in (CODE, NUMBER): raise RuntimeViolation("%s requires stream and codepoint on the stack" % WRITE)
    value = bytes(bytearray([int(getNumber(value))]))
    argument[None].write(value if argument[None] not in (sys.stdout, sys.stderr) else value.decode(sys.stdout.encoding))  # locale.getpreferredencoding()
    if argument[None] in (sys.stdout, sys.stderr): argument[None].flush()
    return

  if token in (IF, NOT):  # common logic
    if not stack: raise RuntimeViolation("%s requires one boolean on the stack" % token)
    value = stack.pop()
    if getType(value) != BOOL: raise RuntimeViolation("%s requires one boolean argument on the stack %r" % (token, fromValue(value)))

    if token == NOT: stack.append(makeBool(not getBool(value))); return

    if token == IF:
      if not getBool(value):
        op = next(tokens)  # if FALSE, don't execute next token (and remove one or two blocks after it for error, assert etc.)
        if op in DEFS:   next(tokens)
        if op == ASSERT: next(tokens)
      return

  if token in (EQ, ) + ORDERED:  # common logic
    assert len(stack) >= 2, "%s requires two arguments on the stack" % token
    b, a = stack.pop(), stack.pop()
    c, d = getType(a), getType(b)
    A, B = fromValue(a), fromValue(b)
    if c is NILT and d is NILT: stack.append(makeBool(True)); return  # nil always equals nil
    if NILT in (c, d): stack.append(makeBool(False)); return  # nil never compares to any other value
    if c != d: raise RuntimeViolation("%s on different data types %r %r" % (token, fromValue(a), fromValue(b)))

    if token == EQ:
      if c in (BOOL, NUMBER, STRING): stack.append(makeBool(A == B if c == d else str(A) == str(B)))
      else: stack.append(makeBool(orderedDictRepresentation(a) == orderedDictRepresentation(b)))
    else:  # if token in ORDERED:  # LE lower or equal, GE greater or equal
      if token == GE: a, b, c, d, A, B = b, a, d, c, B, A  # reverse arguments to keep rest of implementation the same
      if c in (NUMBER, STRING): stack.append(makeBool(A <= B if c == d else str(A) <= str(B)))
      else: stack.append(makeBool(orderedDictRepresentation(a) <= orderedDictRepresentation(b)))
    return

  if token in NUMERICS + BITWISE:  # + - * //
    assert len(stack) >= 2, "numeric operation %s requires two arguments on the stack" % token
    b, a = stack.pop(), stack.pop()
    try: a, b = getNumber(a), getNumber(b)
    except: raise RuntimeViolation("numeric operation %s with wrong data types on stack %r %r" % (token, fromValue(a), fromValue(b)))
    try:
      if   isinstance(a, decimal.Decimal) and isinstance(b, fractions.Fraction): b = decimal.Decimal(b.numerator) / decimal.Decimal(b.denominator)
      elif isinstance(b, decimal.Decimal) and isinstance(a, fractions.Fraction): a = decimal.Decimal(a.numerator) / decimal.Decimal(a.denominator)
      else:  # no decimal
        if   isinstance(a, fractions.Fraction) and isinstance(b, int): b = fractions.Fraction(b)
        elif isinstance(b, fractions.Fraction) and isinstance(a, int): a = fractions.Fraction(a)
      if token in BITWISE and not (isinstance(a, int) and isinstance(b, int)): raise RuntimeViolation("bit operation %s requires integers %r %r" % (token, a, b))
      if   token == BAND:  c = a & b
      elif token == BOR:   c = a | b
      elif token == BXOR:  c = a ^ b
      elif token == PLUS:  c = a + b
      elif token == MINUS: c = a - b
      elif token == TIMES: c = a * b
      elif token == DIVMOD:
        if isinstance(a, int) and isinstance(b, int): a, b = fractions.Fraction(a),  fractions.Fraction(b)
        c = a / b
        d = a % b
        if not isinstance(d, int) and d == int(d): d = int(d)  # convert down - avoid complex fractional representation
        stack.append(makeNumber(d))
      if not isinstance(c, int) and c == int(c): c = int(c)  # convert down
      stack.append(makeNumber(c))
    except (decimal.ConversionSyntax, decimal.DecimalException, decimal.InvalidOperation, ArithmeticError) as E: raise RuntimeViolation(E)
    return

  if token == ALIAS:
    block = next(tokens)
    name = block[0]
    if debug: print("NAME " + name)
    if name in aliases: raise RuntimeViolation("%s %s already defined%s" % (token, name))
    aliases[name] = block[1:]
    return

  if token == DEF:
    name = next(tokens)  # get static function name
    if debug: print("NAME " + name)
    namespaces[-1][name] = statics[name]  # store reference to static function tokens in current namespace
    namespaces[-1][name].name = name
    return

  if token == DYNDEF:
    block = next(tokens)
    name, inputs, outputs = block[0], int(block[1]), next(tokens)
    if debug: print("NAME " + name)
    func = compileFunction(token, name, inputs, block[2:], outputs)
    namespaces[-1][name] = func  # store function in current namespace
    namespaces[-1][name].name = name
    return

  if token == ASSERT:
    expect, test = next(tokens), next(tokens)  # consume next two blocks
    if optimize: return  # skip running tests
    global sut
    isstack, exstack, oldstatics, sut = [], [], copy.copy(statics), True  # always enable debug output during asserts
    try: error = interpret(TokenIter(test),   [{k: copy.deepcopy(v) if not callable(v) and v.get(TYPE, -999) != FILE else v for k, v in namespace.items()} for namespace in namespaces], isstack)
    except RuntimeViolation as E: error = str(E)
    if error: isstack.append(makeString("ERROR " + error))
    if debug: print("STWAS " + stackStr(isstack, sep = SEP))
    statics = oldstatics
    try: error = interpret(TokenIter(expect), [{k: copy.deepcopy(v) if not callable(v) and v.get(TYPE, -999) != FILE else v for k, v in namespace.items()} for namespace in namespaces], exstack)
    except RuntimeViolation as E: error = str(E)
    if error: exstack.append(makeString("ERROR " + error))
    if debug: print("STEXP " + stackStr(exstack, sep = SEP))
    statics, sut, E = oldstatics, False, None  # don't keep any compiled functions
    try:
      if not(len(isstack) == len(exstack) and all([(
        (str(fromValue(i)).startswith("ERROR") and str(fromValue(e)).startswith("ERROR"))) or (str(fromValue(i)) == str(fromValue(e)))
        for i, e in zip(isstack, exstack)])
      ):
        E = "SHOULD %s(%d) BUT WAS %s(%d) for %s %s\nTOKENS:\n- %s\nSTACKS:\n- %s" % (
            stackStr(exstack), len(exstack),
            stackStr(isstack), len(isstack),
            formatCodeBlock(test),
            ".".join(callstack),
            "\n- ".join(lastCalls) if displayFifo else "",
            "\n- ".join([stackStr(s, sep = " ") for s in lastStacks]) if displayFifo else ""
          )
    except Exception as E: pass
    if E:
      try: print("FAILD %s in %s" % (E, test) + "\nSTWAS " + stackStr(isstack, sep = SEP) + repr(isstack))
      except: print("ERROR %r" % test)
      if '--interactive' in sys.argv: import pdb; pdb.set_trace()
    return

  if token == DEBUG: name = next(tokens); debug = True if name == ON else (name if name != OFF else False); return

  if token == GROUP: block = next(tokens); return interpret(TokenIter(block), namespaces, stack, breaker = BREAK)

  if token == NEWLIST: stack.append(fromLiteral(next(tokens))); return  # literal list

#  if token == DYNLIST: lizt = next(tokens); stack.append(lizt); return  # TODO implement dynamic lists

  try: stack.append(fromLiteral(token)); return  # attempt to interpret as a number
  except ParsingError as E: pass

  # variable references and functions
  if token == APPLY:
    if not stack: raise RuntimeViolation("%s requires one function reference on the stack %s" % (token, stackStr(stack, sep = " ")))
    func = stack.pop()
    if getType(func) != FUNC: raise RuntimeViolation("apply requires one function reference on stack " + stackStr(stack, sep = " "))
    token = getString(func, allowed_types = (FUNC,))

  count = 1
  while token[0] == DOT:
    count += 1; token = token[1:]
    if count > len(namespaces): raise RuntimeViolation("cannot dereference parent namespace beyond global namespace")
  for namespace in namespaces[-count:-len(namespaces)-1:-1]:  # from local to global
    if (token if DOT not in token else token[:token.index(DOT)]) in namespace:  # function call or variable
      if token in namespace and callable(namespace[token]): return namespace[token](tokens, namespaces, stack)  # call the function
      stack.append(getVariable(namespace, token))  # put variable (sub-structure) on TOS
      return

  if debug:
    print("-" * 40)
    print(namespaceStr(namespaces))
    print("STACK " + stackStr(stack, sep = SEP))
    print("ERROR Unknown symbol %r" % token)
  return "Unknown symbol %r" % token  # return non-None value here to let interpret() raise the exception


def tokenize(data):
  ''' Split the file data into textual fragments (tokens), accompanied with a line number it originates. '''
  lines = data.replace("\r\n", "\n").split("\n")  # line-wise
  return reduce(lambda a, b: a + b, [[(l + 1, t) for t in line.strip().split(SPACE) if t != '' and not t.startswith('```')] + [(l + 1, EOL)] for l, line in enumerate(lines)], [])


def fromLiteral(token):
  ''' Create internal representation from the literal token string.
  >>> debug = True; fromLiteral('nil')
  {'type': 0}
  >>> debug = True; orderedDictRepresentation(fromLiteral(['1', 'True']))
  "[('0', [('0', 49), ('num', 1), ('type', 2)]), ('1', [('0', -1), ('type', 1)]), ('num', 2), ('type', 4)]"
  '''
  if isinstance(token, list): return makeList([fromLiteral(_) for _ in token if _ != NEWLIST])  # ignore [ since following list always treated right
  if token    == NIL:    return {TYPE: NILT}  # create a new object on every call to allow subsequent modification (e.g. in map-create)
  if token    in TRUTH:  return makeBool(token == TRUE)
  if token[0] == QUOTE:  return makeString(token[1:-1])
  if token[0] == SYMBOL: return makeString(token[1:])
  if token[0] == REF:    return makeReference(token[1:])
  return makeNumber(parseNumber(token))


def parseFile(file, tokens, i = -1, until = END, untilBefore = None, comments = True):
  ''' Combine the tokens and perform syntax checks. Return a list of tokens and further nested lists, and the (next) token counter. '''
  def Error(message, kwargs): raise ParsingError((message + " in file {file} on line {l}").format(**kwargs))  # reused exception
  n, t, x = len(tokens), [], None
  while True:
    i += 1
    if i >= n: break
    l, x = tokens[i]
    if displayTokens: print("%15s %4d %s" % (file.replace(".awfl", ""), l, x))
    if   x == until: break  # end inner list (def, alias, from) or block (error, break), itself not added to tokens. must come before next case:
    elif x == untilBefore: i -= 1; break
    if x.startswith(until): Error("{x} looks like a syntax error (missing space?)", vars())
    elif x is EOL: continue  # not needed, because error and break blocks will be constructed as lists until end of line
    if x[0] == COMMENT:
      comment = x
      while tokens[i + 1][1] is not EOL: i += 1; comment += SPACE + tokens[i][1]
      if comments: t.extend([comment] if not optimize else [] + [EOL])
    elif x[0] in (DOT, REF, SYMBOL):
      if len(x.replace(DOT, "").replace(REF, "").replace(SYMBOL, "")) < 1: Error("%s {x} syntax error" % {DOT: "parent variable reference", REF: "reference", SYMBOL: "symbol"}[x[0]], vars())
      t.append(x)
    elif x[0] == QUOTE:
      quote = [x]
      while quote == ['"'] or quote[-1].endswith(ESCAPE) or not quote[-1].endswith(QUOTE): quote.append("\n" if tokens[i + 1][1] is EOL else (SPACE + tokens[i + 1][1])); i += 1
      t.append("".join(quote).replace(ESCAPE, QUOTE))  # add including quotes but un-escape inner quotes
    elif x == INCLUDE:
      if displayTokens: print("%15s %4d %s" % ("", l, tokens[i+1][1]))
      insert = include(tokens[i + 1][1], file, l)
      tokens = tokens[:i] + insert + [(l, "# EOI %s" % tokens[i+1][1])] + tokens[i + 2:]  # extend unparsed token stream by included file's tokens
      i -= 1; n += len(insert) - 1  # removed 2 tokens, but inserted 1 comment
    elif x in VARIABLES:
      if i + 1 >= n: Error("{x} without symbol following", vars())
      if len(tokens[i + 1][1].replace(DOT, "")) < 1: Error("{x} argument syntax", vars())
      if tokens[i + 1][1].replace(DOT, "") in RESERVED_KEYWORDS: Error("{x} using reserved symbol %s" % tokens[i + 1][1], vars())
      t.append(x)
    elif x in DEFS:
      t.append(x)  # mark the meaning of the following list (or function name) with the opening symbol
      if x in NAMEDEFS and i + 1 >= n: Error("{x} without name", vars())  # alias, (dyn)def
      if x in NAMEDEFS and tokens[i + 1][1] in RESERVED_KEYWORDS: Error("{x} name is a reserved symbol %s" % tokens[i + 1][1], vars())
      u, i = parseFile(file, tokens, i, DEFS[x], untilBefore = ENDGROUP if x == BREAK else None, comments = x not in (NEWLIST, GROUP))  # recursive list parsing
      if len(u) < {ALIAS: 2, DEF: 3, DYNDEF: 3}.get(x, 0): Error("{x} body with insufficient contents (forgot a closing keyword earlier?)", vars())
      if x != DEF: t.append(u)  # add recursive list
      if x == ERROR and "".join([u[0][0], u[0][-1]]) != '""': Error("{x} without error message" , vars())
      elif x in (DEF, DYNDEF):
        if not isinstance(u[0], str): Error("{x} name missing", vars())
        if not isinstance(u[1], str): Error("{x} #inputs missing", vars())
        try: int(u[1])
        except (TypeError, ValueError) as E: Error("{x} #inputs syntax {E}", vars())
        if not isinstance(tokens[i + 1][1], str): Error("{x} #outputs missing", vars())
        try: int(tokens[i + 1][1]) if tokens[i + 1][1] != UNKNOWN else UNKNOWN  # nil means any number of output
        except (TypeError, ValueError) as E: Error("{x} #outputs syntax {t} {E}", {"x": x, "t": tokens[i + 1][1], "file": file, "l": tokens[i + 1][0], "E": E})
      elif x == ASSERT:  # second block of assert
        u, i = parseFile(file, tokens, i, DEFS[FROM])
        if len(u) == 0: Error("%s body with insufficient contents" % FROM, vars())
        t.append(u)  # parse second part of assert
      if x == DEF:
        statics[u[0]] = compileFunction(x, u[0], int(u[1]), u[2:], tokens[i + 1][1]); i += 1  # store function in static map
        t.append(u[0])  # store info about the function definition in the token stream, so the runtime interpreter can put it in the namespace
    elif x == IGNORE:  # ignore everything until "ignore off"
      i += 1
      if i >= n: Error("{x} requires one argument", {"x": x, "file": file, "l": tokens[i + 1][0]})
      if tokens[i][1] not in (ON, OFF): Error("syntax error {g}", {"file": file, "l": tokens[i][0], "g": "ignore " + tokens[i][1]})
      if tokens[i][1]     ==      OFF: continue  # nothing to do
      while i + 1 < n and not (tokens[i + 1][1] == IGNORE and tokens[i + 2][1] == OFF): i += 1
      i += 2
    elif x == DEBUG:
      t.append(x); i += 1
      if i >= n: Error("{x} requires one argument", {"x": x, "file": file, "l": tokens[i + 1][0]})
      if tokens[i][1] not in (ON, OFF, THIS): Error("{x} wrong argument {y}", {"x": x, "y": tokens[i][1], "file": file, "l": tokens[i][0]})
      t.append(tokens[i][1])
    elif len(x.replace(DOT, "")) == 0: Error("syntax error {x}", vars())
    else: t.append(x)
  return t, i

standard = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), LIBS)
def include(name, file, line):
  if name in includes: return []  # skip already included files, return no new tokens
  includes.add(name)  # allows mutually recursive including
  if name + ".awfl" in os.listdir(standard): path = os.path.join(standard, name)
  elif os.path.exists(name.strip(".").replace(".", os.sep) + ".awfl"): path = name.strip(".").replace(".", os.sep)
  else: raise ParsingError("include %r (transitively) missing from file %s on line %d" % (name, file, line))
  if debug: print("INCLD " + name)
  with open(path + ".awfl", "r", encoding = "utf-8") as fd: data = fd.read()  # slurp entire file
  tokens = tokenize(data)
  if debug: print("Loaded %d tokens from %r" % (len(tokens), path))
  maxline = max(dict(tokens).keys()) + 1  # add virtual last line
  tokens += [_ for _ in zip([maxline, maxline, maxline], ["ignore", "off", EOL])]  # ensure that ignore area ends after each file
  return tokens


if __name__ == '__main__':
  if '--help' in sys.argv: print("""AWFUL V%s  (C) 2019-2020 Arne Bachmann

python[3] [-O] awfl.py [file1.awfl [file2.awfl [...]]] [<options>]

-O               Remove Python assert statements from runtime
--optimize       Remove Awful comments and asserts
--decimals <n>   Set decimal computation precision to n digits (default: 1000)
--run "token s"  Run given AWFUL commands and quit
--repl           Start interactive AWFUL shell after processing given files
--help           Show this interpreter options

Debugging:
--warn           Show runtime warnings to find code problems
--debug          Show parser info and enable live debugger
--calls          Display call hierarchy
--names          Display all words in all namespaces
--tokens         Display tokens at parsetime
--fifo           Display last 15 tokens and stacks in case of error
--stats          Show interpreter run statistics before interpreter shutdown
--interactive    In case of test case failure, drop into a python debug shell
--test           Run test cases

Keywords and symbols:
  Values:     nil False True "
  Grouping:   ( ) [ ![ ]
  Maths:      + - * //
  Stack:      nib bin pop dup
  Functions:  def dyndef end & alias apply
  Logic:      not if eq le ge as up rm
  Structures: . pull push pushi
  Files:      open create close read write
  Control:    break error
  Testing:    assert from debug ignore on off\n""" % VERSION); sys.exit(0)

  debug, counter, calls, start_ts, statics, sut, lastCalls, lastStacks = False, 0, 0, time.time(), {}, False, Queue(), Queue()
  error, count = doctest.testmod()  # must define debug here to have it in test cases
  if '--test'     in sys.argv: sys.exit(0)
  if '--decimals' in sys.argv: index = sys.argv.index('--decimals'); decimal.getcontext().prec = int(sys.argv[index + 1]); del sys.argv[index:index+2]  # define decimal precision before applying float techniques
  else: decimal.getcontext().prec = 1000
  if error != 0: raise Exception("%d out of %d self-tests failed" % (error, count))
  callstack, includes, stack, namespaces, aliases, optimize, items = [], set(), [], [{}], {}, '--optimize' in sys.argv, []  # stack and global namespace
  debug, warn, displayTokens, displayNamespaces, displayCallstack, displayFifo = [_ in sys.argv for _ in ('--debug', '--warn', '--tokens', '--names', '--calls', '--fifo')]
  size = lambda l: sum([1 if not isinstance(_, list) else size(_) for _ in l]); assert 5 == size([1, 2, 3, [3, 4]])
  files = [_ for _ in sys.argv[1:] if _.endswith(".awfl")]
  if len(files) == 0 and '--repl' not in sys.argv: print("No files specified"); sys.exit(1)
  if files and debug: print("Running files: %s" % " ".join(files))
  for file in files:
    tokens = include(file.rstrip(".awfl"), file, 0)
    _ = parseFile(file, tokens); items.extend(_[0])
    if debug: print("Parsed %d items from %r" % (size(items), file))
  try:
    error = interpret(TokenIter(items), namespaces, stack)
  except RuntimeViolation as E: error = str(E)
  if '--repl' in sys.argv:
    print("Awful REPL. Enter 'quit' to exit.")
    count = 0
    while True:
      count += 1
      items = input("%4d-> " % count).replace("\n", " ").replace("\r", "")
      if items in ("exit", "quit"): break
      try:
        tokens = tokenize(items)
        items, _ = parseFile("repl", tokens)
        error = interpret(TokenIter(items), namespaces, stack)
      except ParsingError as E: print(str(E))
      if error: print(repr(error))
      print("STACK " + stackStr(stack, sep = SEP))
  elif '--run' in sys.argv:
    items = " ".join([_.strip('"') for _ in sys.argv[sys.argv.index('--run') + 1:]])
    tokens = tokenize(items)
    items, _ = parseFile("repl", tokens)
    error = interpret(TokenIter(items), namespaces, stack)
    if error: print(repr(error))
  if error: print(namespaceStr(namespaces))
  if stack: print("STACK " + stackStr(stack, sep = SEP))
  if error: print("ERROR " + error)
  if '--stats' in sys.argv:
    print("Number of instructions processed: %d (%.0f/s)" % (counter, counter / (time.time() - start_ts)))
    print("Number of function calls:         %d (%.0f/s)" % (calls, calls / (time.time() - start_ts)))
    print("Runtime:                          %.2f s"      % (time.time() - start_ts))
