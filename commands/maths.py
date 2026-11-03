import ast
import html
import math
import operator

from telegram import Update
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import format_number, get_args, parse_number, usage

MAX_RESULT_DIGITS = 10_000
MAX_FACTORIAL = 1_000
MAX_FIBONACCI = 10_000
MAX_PRIME = 10 ** 24
# Bases de Miller-Rabin deterministas hasta 3.3e24.
PRIME_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)

OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def safe_factorial(value: float) -> int:
    """Factorial limitado para evitar cálculos enormes."""
    if not float(value).is_integer() or not 0 <= value <= MAX_FACTORIAL:
        raise UserError(f"factorial solo admite enteros entre 0 y {MAX_FACTORIAL}")
    return math.factorial(int(value))


FUNCTIONS = {
    name: getattr(math, name) for name in (
        "sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "log", "log10", "log2", "exp",
        "floor", "ceil", "radians", "degrees",
    )
} | {"abs": abs, "round": round, "factorial": safe_factorial}


def evaluate(node: ast.AST) -> int | float:
    """Evalúa de forma segura un árbol de expresión aritmética."""
    match node:
        case ast.Expression(body=body):
            return evaluate(body)
        case ast.Constant(value=int() | float() as value) if not isinstance(value, bool):
            return value
        case ast.Name(id=name) if name in CONSTANTS:
            return CONSTANTS[name]
        case ast.UnaryOp(op=op, operand=operand) if type(op) in OPERATORS:
            return OPERATORS[type(op)](evaluate(operand))
        case ast.BinOp(left=left, op=op, right=right) if type(op) in OPERATORS:
            a, b = evaluate(left), evaluate(right)
            if isinstance(op, ast.Pow) and abs(a) > 1 and b * math.log10(abs(a)) > MAX_RESULT_DIGITS:
                raise UserError("El resultado es demasiado grande")
            return OPERATORS[type(op)](a, b)
        case ast.Call(func=ast.Name(id=name), args=args, keywords=[]) if name in FUNCTIONS:
            return FUNCTIONS[name](*(evaluate(arg) for arg in args))
    raise UserError("Expresión no soportada")


def format_result(value: int | float) -> str:
    """Formatea el resultado del cálculo."""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() and abs(value) < 1e15 else f"{value:.12g}"
    if value == 0 or math.log10(abs(value)) < 3000:
        return str(value)
    exponent: int = math.floor(math.log10(abs(value)))
    mantissa: float = 10 ** (math.log10(abs(value)) - exponent)
    return f"≈ {'-' if value < 0 else ''}{mantissa:.10f}E+{exponent}"


@handle_errors("Error al evaluar la expresión")
async def calculate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Evalúa una expresión matemática."""
    expression: str = get_args(update)
    if not expression:
        raise usage("/calculate <expresion>")
    normalized: str = expression.replace("^", "**").replace("×", "*").replace("÷", "/")
    try:
        result: int | float = evaluate(ast.parse(normalized, mode="eval"))
    except SyntaxError:
        raise UserError("Expresión mal formada")
    except ZeroDivisionError:
        raise UserError("División entre cero")
    except (OverflowError, ValueError, TypeError) as e:
        raise UserError(f"No se puede calcular: {html.escape(str(e))}")
    await update.effective_message.reply_text(
        f"🧮 <code>{html.escape(expression)}</code>\n= <b>{format_result(result)}</b>"
    )


def is_prime(n: int) -> bool:
    """Test de primalidad de Miller-Rabin determinista."""
    if n < 2:
        return False
    for p in PRIME_BASES:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d, s = d // 2, s + 1
    for a in PRIME_BASES:
        x: int = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def parse_integer(value: str, command: str) -> int:
    """Convierte el argumento en entero o muestra el uso."""
    try:
        return int(value)
    except ValueError:
        raise usage(command)


@handle_errors("Error al comprobar el número")
async def prime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comprueba si un número entero es primo."""
    n: int = parse_integer(get_args(update), "/prime <numero>")
    if abs(n) > MAX_PRIME:
        raise UserError("El número es demasiado grande (máximo 10^24)")
    result: str = "✅ es primo" if is_prime(n) else "❌ no es primo"
    await update.effective_message.reply_text(f"<b>{n}</b> {result}")


@handle_errors("Error al calcular Fibonacci")
async def fibonacci(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Calcula el n-ésimo número de Fibonacci."""
    n: int = parse_integer(get_args(update), "/fibonacci <numero>")
    if not 0 <= n <= MAX_FIBONACCI:
        raise UserError(f"El número debe estar entre 0 y {MAX_FIBONACCI}")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    await update.effective_message.reply_text(f"🌀 F({n}) = <code>{a}</code>")


@handle_errors("Error al calcular el porcentaje")
async def percent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Calcula qué porcentaje representa una parte sobre el total."""
    args: list[str] = get_args(update).split()
    if len(args) != 2:
        raise usage("/percent <parte> <total>")
    part, total = parse_number(args[0]), parse_number(args[1])
    if total == 0:
        raise UserError("El total no puede ser cero")
    await update.effective_message.reply_text(
        f"📊 {format_number(part)} es el <b>{format_number(part / total * 100)} %</b> de {format_number(total)}"
    )
