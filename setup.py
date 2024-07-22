import setuptools

setuptools.setup(
    name="backup_script",
    version="1.0.0",
    description="A backup script module",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "aiofiles==24.1.0",
        "fire==0.6.0",
        "GitPython==3.1.43",
        "loguru==0.7.2",
        "tabulate==0.9.0",
        "tqdm==4.66.4",
    ],
    extras_require={
        "dev": [
            "iniconfig==2.0.0",
            "pytest==8.2.2",
            "pytest-asyncio==0.23.8",
            "mypy==1.10.1",
        ]
    },
)
