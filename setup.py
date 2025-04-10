from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in agastya_agro/__init__.py
from agastya_agro import __version__ as version

setup(
	name="agastya_agro",
	version=version,
	description="Agastya Agro",
	author="Dexciss",
	author_email="vsolanke@dexciss.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
