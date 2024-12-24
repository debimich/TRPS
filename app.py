from flask import Flask, render_template, request, send_from_directory, url_for
from PIL import Image, ImageDraw
from pyparsing import Word, alphas, alphanums, oneOf, Group, Forward, infixNotation, opAssoc
import random
from io import BytesIO
import os

app = Flask(__name__)

class Utility:
	@staticmethod
	def precedence(op):
		priorities = {'~': 3, '&': 2, '|': 1}
		return priorities.get(op, 0)

	@staticmethod
	def infix_to_postfix(expression):
		stack = []
		result = []
		i = 0

		while i < len(expression):
			char = expression[i]

			if char.isalnum():
				operand = ''
				while i < len(expression) and expression[i].isalnum():
					operand += expression[i]
					i += 1
				result.append(operand)
				continue
			elif char == '(':
				stack.append(char)
			elif char == ')':
				while stack and stack[-1] != '(':
					result.append(stack.pop())
				stack.pop()
			elif char in ('&', '|', '~'):
				while (stack and stack[-1] != '(' and
					Utility.precedence(stack[-1]) >= Utility.precedence(char)):
					result.append(stack.pop())
				stack.append(char)

			i += 1

		while stack:
			result.append(stack.pop())

		return result

	@staticmethod
	def check_parser(expression):
		identifier = Word(alphas, alphanums)
		operator = oneOf("& | ~")
		expr = Forward()

		atom = identifier | Group("(" + expr + ")")
		expr <<= infixNotation(atom, [
			("~", 1, opAssoc.RIGHT),
			("&", 2, opAssoc.LEFT),
			("|", 2, opAssoc.LEFT),
		])

		try:
			expr.parseString(expression, parseAll=True)
			return True
		except Exception:
			return False

class Wire:
	def __init__(self, name, x, y):
		self.name = name
		self.x = x
		self.y = y

	def draw_line(self, draw_obj):
		draw_obj.line((self.x, self.y, self.x - 20, self.y), fill="black", width=2)

	def draw_text(self, draw_obj):
		draw_obj.text((self.x - 15, self.y - 20), self.name, fill="black")

class LogicElement:
	def __init__(self, type, output, x, y):
		self.type = type
		self.x = x
		self.y = y
		self.width = 30
		self.height = 50
		self.wire = Wire(output, self.x + self.width // 2 + 20, self.y)

	def draw(self, draw_obj):
		top_left = (self.x - self.width // 2, self.y - self.height // 2)
		bottom_right = (self.x + self.width // 2, self.y + self.height // 2)
		draw_obj.rectangle([top_left, bottom_right], outline="black", width=2)
		
		if self.type == '~':
			circle_center = (self.x + self.width // 2, self.y)
			draw_obj.ellipse([(circle_center[0] - 5, circle_center[1] - 5),
							(circle_center[0] + 5, circle_center[1] + 5)],
							outline="black", width=2)

		symbol = self.type if self.type == '&' else '1'
		draw_obj.text((self.x, self.y - 20), symbol, fill="black")
		self.wire.draw_line(draw_obj)

class Circuit:
	def __init__(self, expression):
		self.expression = expression
		self.wires = []

	def connect(self, x1, y1, x2, y2, draw_obj):
		rand = random.randint(0, 30)
		draw_obj.line([x1, y1, x1 + rand, y1], fill="black", width=2)
		x1 += rand

		if x1 == x2:
			draw_obj.line([x1, y1, x2, y2], fill="black", width=2)
		elif y1 == y2:
			draw_obj.line([x1, y1, x2, y2], fill="black", width=2)
		else:
			draw_obj.line([x1, y1, x1, y2], fill="black", width=2)
			draw_obj.line([x1, y2, x2, y2], fill="black", width=2)

	def create_circuit(self):
		if not Utility.check_parser(self.expression):
			print("Неправильно введена функция")
			return

		postfix_expression = Utility.infix_to_postfix(self.expression.replace(" ", ""))
		operands = sorted(set(postfix_expression) - {'~', '|', '&'})
		operators_num = sum(1 for element in postfix_expression if element in {'&', '|', '~'})

		width = max(operators_num * 200, 200)
		height = max(1000, 1000)
		img = Image.new("RGB", (width, height), "white")
		draw = ImageDraw.Draw(img)

		for i, operand in enumerate(operands):
			wire = Wire(operand, 30, i * 100 + 50)
			wire.draw_line(draw)
			wire.draw_text(draw)
			self.wires.append(wire)

		stack = []
		counter = 0
		exist_nums = []

		for char in postfix_expression:
			if char.isalnum():
				stack.append(char)
			elif char in ('~', '&', '|'):
				operands_data = [stack.pop() for _ in range(2 if char in ('&', '|') else 1)]
				coords = [(w.x, w.y) for w in self.wires if w.name in operands_data]
				element_x = 120 + counter * 200
				element_y = coords[0][1] + 10 if len(coords) > 1 else coords[0][1]

				while any(abs(element_y - num) <= 39 for num in exist_nums):
					element_y += 40
				exist_nums.append(element_y)

				result = f"T{counter}"
				element = LogicElement(char, result, element_x, element_y)
				element.draw(draw)
				self.wires.append(element.wire)

				if char in ('&', '|'):
					self.connect(coords[0][0], coords[0][1], element.x - 15, element.y - 10, draw)
					self.connect(coords[1][0], coords[1][1], element.x - 15, element.y + 10, draw)
				else:
					self.connect(coords[0][0], coords[0][1], element.x - 15, element.y, draw)

				counter += 1
				stack.append(result)

		max_y = max(exist_nums) if exist_nums else 100
		resized_img = Image.new("RGB", (width, max(max_y + 50, len(operands) * 100)), "white")
		resized_img.paste(img, (0, 0))
		path_to_save = os.path.join('static', 'images', 'circuit.png')
		resized_img.save(path_to_save)
		return path_to_save

@app.route("/", methods=["GET", "POST"])
def index():
	error = None
	image_url = None
	expression = ""
	
	if request.method == "POST":
		expression = request.form.get("expression")
		
		if not Utility.check_parser(expression):
			error = "Ошибка: Неправильный формат булевой функции. Проверьте ввод."
		else:
			circuit = Circuit(expression)
			image_url = circuit.create_circuit()
			if not image_url:
				error = "Ошибка при построении схемы. Попробуйте снова."
	
	return render_template("index.html", image_url=image_url, error=error, expression=expression)

if __name__ == "__main__":
	app.run(debug=True)
