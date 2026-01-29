from setuptools import setup, find_packages

setup(
    name="mbta_led_controller",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "Flask>=2.0.0",
        "requests>=2.25.0",
        "sseclient>=0.0.27",
        "python-dotenv>=0.19.0",
        "rpi-ws281x>=4.3.0",
        "adafruit-blinka>=6.0.0",
        "adafruit-circuitpython-neopixel>=6.0.0",
        "board>=1.0",
        "pytz>=2021.1",
        "RPi.GPIO",
    ],
) 