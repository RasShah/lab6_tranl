# Установка и сборка

Проект использует Python 3.10+, GNU Bison 3.8+, Flex 2.6+ и GCC/Clang
с поддержкой C11. Сборка управляется Python; CMake, Java и pip-пакеты
для неё не нужны.

## Windows: MSYS2

1. Установите Python с [python.org](https://www.python.org/downloads/windows/)
   и MSYS2 с [msys2.org](https://www.msys2.org/).
2. В терминале **MSYS2 UCRT64** установите инструменты:

```bash
pacman -S --needed bison flex mingw-w64-ucrt-x86_64-gcc
```

Пакеты [Bison](https://packages.msys2.org/packages/bison) и
[Flex](https://packages.msys2.org/packages/flex) устанавливаются в `usr/bin`,
GCC UCRT64 — в `ucrt64/bin`.

После этого в обычном PowerShell, из каталога проекта:

```powershell
python scripts/build_native.py
python main.py examples/valid/basic.mini
python run_tests.py
```

Если MSYS2 находится в `C:\msys64`, скрипт обнаружит программы автоматически.
Для другой папки укажите её:

```powershell
$env:MSYS2_ROOT = "D:\msys64"
python scripts/build_native.py
```

## Явные пути к программам

```powershell
$env:BISON = "C:\msys64\usr\bin\bison.exe"
$env:FLEX = "C:\msys64\usr\bin\flex.exe"
$env:CC = "C:\msys64\ucrt64\bin\gcc.exe"
python scripts/build_native.py
```

Переменные содержат путь к исполняемому файлу, без дополнительных аргументов.
Поддерживаются также `win_bison.exe` и `win_flex.exe` из
[WinFlexBison](https://github.com/lexxmark/winflexbison).
Для `win_flex` автоматически включается `--wincompat`.
Компилятор должен поддерживать командную строку GCC/Clang; `cl.exe`
из Visual Studio этой командой сборки не поддерживается.

## Linux: Debian / Ubuntu

```bash
sudo apt update
sudo apt install python3 bison flex gcc libc6-dev
python3 scripts/build_native.py
python3 main.py examples/valid/basic.mini
python3 run_tests.py
```

Убедитесь, что установленная версия Python не ниже 3.10, а Bison — не ниже 3.8.

## Как выполняется сборка

Скрипт запускает три шага из корня проекта. Их эквивалент в терминале,
когда инструменты доступны в `PATH` и каталог `build` уже создан:

```bash
bison --warnings=all,error --defines=build/parser.h --output=build/parser.c --report=state --report-file=build/parser.output files/mini.y
flex --outfile=build/lexer.c files/mini.l
gcc -std=c11 -O2 -Wall -Wextra -Werror -Inative -Ibuild build/parser.c build/lexer.c native/ast.c native/main.c -o build/analyzer_native
```

На Windows выходной файл имеет расширение `.exe`.
Для работы с WinFlexBison замените имена программ и добавьте `--wincompat`
к команде `win_flex`.

Промежуточные C-файлы генерируются заново. Готовый исполняемый файл заменяется
только после успешной компиляции. Хеш исходников в `build/source.sha256`
позволяет пропустить повторную сборку при обычном запуске.

Если анализатор сообщает, что инструмент не найден, проверьте `PATH`
либо задайте явные пути выше. Для принудительной пересборки после обновления
инструментов используйте `python main.py --build`.
