import re
import json
import click
import subprocess

from pathlib import Path
from .utils import create_file
from .boilerplates import *


class SPAGenerator:
	def __init__(self, spa_name, app, add_tailwindcss):
		"""Initialize a new SPAGenerator instance"""
		self.app = app
		self.app_path = Path("../apps") / app
		self.spa_name = spa_name
		self.spa_path: Path = self.app_path / self.spa_name
		self.add_tailwindcss = add_tailwindcss

	def generate_spa(self):
		click.echo("Generating spa...")

		self.initialize_vue_vite_project()
		self.link_controller_files()
		self.setup_proxy_options()
		self.setup_vue_router()
		self.create_vue_files()
		self.update_package_json()
		self.create_www_directory()

		if self.add_tailwindcss:
			self.setup_tailwindcss()

		self.add_routing_rule_to_hooks()

		click.echo(f"Run: cd {self.spa_path.absolute()} && npm run dev")
		click.echo("to start the development server and visit: http://<site>:8080")

	def setup_tailwindcss(self):
		# TODO: Convert to yarn command
		# npm install -D tailwindcss@latest postcss@latest autoprefixer@latest
		subprocess.run(
			[
				"npm",
				"install",
				"-D",
				"tailwindcss@latest",
				"postcss@latest",
				"autoprefixer@latest",
			],
			cwd=self.spa_path,
		)

		# npx tailwindcss init -p
		subprocess.run(["npx", "tailwindcss", "init", "-p"], cwd=self.spa_path)

		# Create an index.css file
		index_css_path: Path = self.spa_path / "src/index.css"

		# Add boilerplate code
		INDEX_CSS_BOILERPLATE = """@tailwind base;
@tailwind components;
@tailwind utilities;
	"""

		create_file(index_css_path, INDEX_CSS_BOILERPLATE)

	def create_vue_files(self):
		app_vue = self.spa_path / "src/App.vue"
		create_file(app_vue, APP_VUE_BOILERPLATE)

		views_dir: Path = self.spa_path / "src/views"
		if not views_dir.exists():
			views_dir.mkdir()

		home_vue = views_dir / "Home.vue"
		login_vue = views_dir / "Login.vue"

		create_file(home_vue, HOME_VUE_BOILERPLATE)
		create_file(login_vue, LOGIN_VUE_BOILERPLATE)

	def setup_vue_router(self):
		# Setup vue router
		router_dir_path: Path = self.spa_path / "src/router"

		# Create router directory
		router_dir_path.mkdir()

		# Create files
		router_index_file = router_dir_path / "index.js"
		create_file(
			router_index_file, ROUTER_INDEX_BOILERPLATE.replace("{{name}}", self.spa_name)
		)

		auth_routes_file = router_dir_path / "auth.js"
		create_file(auth_routes_file, AUTH_ROUTES_BOILERPLATE)

	def initialize_vue_vite_project(self):
		# Run "yarn create vite {name} --template vue"
		print("Scafolding vue project...")
		subprocess.run(
			["yarn", "create", "vite", self.spa_name, "--template", "vue"], cwd=self.app_path
		)

		# Install router and other npm packages
		# yarn add vue-router@4 socket.io-client@2.4.0
		print("Installing dependencies...")
		subprocess.run(
			["yarn", "add", "vue-router@^4", "socket.io-client@^2.4.0"], cwd=self.spa_path
		)

	def link_controller_files(self):
		# Link controller files in main.js
		print("Linking controller files...")
		main_js: Path = self.app_path / f"{self.spa_name}/src/main.js"

		if main_js.exists():
			with main_js.open("w") as f:
				boilerplate = MAIN_JS_BOILERPLATE

				# Add css import
				if self.add_tailwindcss:
					boilerplate = "import './index.css';\n" + boilerplate

				f.write(boilerplate)
		else:
			click.echo("src/main.js not found!")
			return

	def setup_proxy_options(self):
		# Setup proxy options file
		proxy_options_file: Path = self.spa_path / "proxyOptions.js"
		create_file(proxy_options_file, PROXY_OPTIONS_BOILERPLATE)

		vite_config_file: Path = self.spa_path / "vite.config.js"
		if not vite_config_file.exists():
			vite_config_file.touch()
		with vite_config_file.open("w") as f:
			boilerplate = VITE_CONFIG_BOILERPLATE.replace("{{app}}", self.app)
			boilerplate = boilerplate.replace("{{name}}", self.spa_name)
			f.write(boilerplate)

	def add_routing_rule_to_hooks(self):
		hooks_py = Path(f"../apps/{self.app}/{self.app}") / "hooks.py"
		hooks = ""
		with hooks_py.open("r") as f:
			hooks = f.read()

		pattern = re.compile(r"website_route_rules\s?=\s?\[(.+)\]")

		rule = (
			"{"
			+ f"'from_route': '/{self.spa_name}/<path:app_path>', 'to_route': '{self.spa_name}'"
			+ "}"
		)

		rules = pattern.sub(r"website_route_rules = [{rule}, \1]", hooks)

		# If rule is not already defined
		if not pattern.search(hooks):
			rules = hooks + "\nwebsite_route_rules = [{rule},]"

		updates_hooks = rules.replace("{rule}", rule)
		with hooks_py.open("w") as f:
			f.write(updates_hooks)

	def update_package_json(self):
		package_json_path: Path = self.spa_path / "package.json"

		if not package_json_path.exists():
			print("package.json not found. Please manulally update the build command.")
			return

		data = {}
		with package_json_path.open("r") as f:
			data = json.load(f)

		data["scripts"]["build"] = (
			f"vite build --base=/assets/{self.app}/{self.spa_name}/ && yarn copy-html-entry"
		)

		data["scripts"]["copy-html-entry"] = (
			f"cp ../{self.app}/public/{self.spa_name}/index.html"
			f" ../{self.app}/www/{self.spa_name}.html"
		)

		with package_json_path.open("w") as f:
			json.dump(data, f, indent=2)

		# Update app's package.json
		app_package_json_path: Path = self.app_path / "package.json"

		if not app_package_json_path.exists():
			subprocess.run(["npm", "init", "--yes"], cwd=self.app_path)

			data = {}
			with app_package_json_path.open("r") as f:
				data = json.load(f)

			data["scripts"]["dev"] = f"cd {self.spa_name} && yarn dev"
			data["scripts"]["build"] = f"cd {self.spa_name} && yarn build"

			with app_package_json_path.open("w") as f:
				json.dump(data, f, indent=2)

	def create_www_directory(self):
		www_dir_path: Path = self.app_path / f"{self.app}/www"

		if not www_dir_path.exists():
			www_dir_path.mkdir()