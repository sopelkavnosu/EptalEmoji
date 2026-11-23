# Eptal Emoji

[Русский](#русский) | [English](#english)

---

## Русский

**Eptal Emoji** — лёгкий и удобный пикер эмодзи для Windows с аккуратным полупрозрачным интерфейсом. Приложение создано для того, чтобы добавлять эмодзи быстро, естественно и без лишних действий — в любом месте, где вы работаете с текстом. Я сам пользуюсь Eptal Emoji каждый день, поэтому приложение развивается вокруг простоты, удобства и реальных сценариев использования.

### Почему это удобно

- **Работает в любом чате и поле ввода** — эмодзи можно вставлять даже там, где нет встроенной панели смайликов или поддержки эмодзи.
- **Практически не требует настройки** — установили, запустили и сразу пользуетесь.
- **Быстрый доступ** — вызывается горячей клавишей `Ctrl+Alt+E` или из системного трея.
- **Ненавязчивый интерфейс** — компактное полупрозрачное окно с тёмным приглушённым фоном не мешает работе и аккуратно смотрится поверх других окон.
- **Свои эмодзи прямо в программе** — можно добавлять собственные смайлики, упорядочивать их и держать под рукой всё самое нужное.

### Возможности

- **Вставка в одно нажатие** — клик по эмодзи копирует его в буфер обмена и пытается вставить в активное поле ввода.
- **Горячая клавиша** — `Ctrl+Alt+E` для быстрого открытия окна.
- **Авто-показ** — при фокусе на текстовом поле окно может появляться автоматически (функция включается/выключается в меню трея).
- **Работа из трея** — значок в области уведомлений: двойной клик открывает/скрывает окно, а меню трея даёт быстрый доступ к настройкам.
- **Поиск и категории** — удобный поиск по названию (en/ru) и категории: «Недавние», «Круглые», «Прир./Еда», «Символы», «Добавл.».
- **Недавние эмодзи** — выбранные смайлики сохраняются в истории для быстрого повторного использования.
- **Свои эмодзи** — добавляйте собственные эмодзи прямо в приложение через кнопку `+`.
- **Управление смайликами** — переносите эмодзи между категориями перетаскиванием и удаляйте ненужные через контекстное меню.
- **Удобное окно** — безрамочный интерфейс, перетаскивание за заголовок, изменение размера, сохранение позиции и настроек.
- **Автозапуск** — при желании можно включить запуск вместе с Windows.

### Скриншоты

Полупрозрачное окно; размер можно изменять по своему вкусу.

![Eptal emoji — полупрозрачное окно](images/screenshot.png)

![Eptal emoji — настраиваемый размер окна](images/screenshot-2.png)

Настройки приложения доступны по правому клику на значок Eptal emoji в области уведомлений (трее).

![Настройки в меню трея](images/settings.png)

### Требования

- Windows
- Python 3.10+ (для запуска из исходников)

Зависимости:
- PyQt6
- emoji
- keyboard
- pyperclip
- uiautomation

### Установка и запуск из исходников

```bash
pip install -r requirements.txt
pythonw eptal_emoji.py
```

### Сборка автономного `.exe` (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --icon=eptal_emoji.ico --name EptalEmoji eptal_emoji.py
```

Готовый файл появится в `dist/EptalEmoji.exe`. Для запуска можно использовать `Start.bat`.

### Использование

- `Ctrl+Alt+E` — показать окно выбора эмодзи.
- Клик по эмодзи — вставка в активное поле (если возможно).
- Кнопка `+` — добавить свои эмодзи.
- Перетаскивание эмодзи на вкладку — перенос между категориями.
- Правый клик по эмодзи — удалить/скрыть смайлик.
- Двойной клик по значку в трее — открыть/скрыть окно.

### Примечания

- Авто-показ по фокусу и авто-вставка зависят от целевого приложения и доступности UI Automation.
- Глобальные горячие клавиши/хуки (`keyboard`) в некоторых случаях могут требовать запуска с повышенными правами.
- История, настройки, добавленные и скрытые эмодзи сохраняются локально в профиле пользователя.

### Лицензия

Проект распространяется по лицензии MIT. См. файл [LICENSE](LICENSE).

---

## English

**Eptal Emoji** is a lightweight and convenient emoji picker for Windows with a clean, semi-transparent interface. It is designed to make adding emojis quick, natural, and effortless — anywhere you work with text. I use Eptal Emoji every day myself, so the app is shaped around simplicity, convenience, and real-world use.

### Why It's Convenient

- **Works in any chat or text field** — you can insert emojis even where there is no built-in emoji panel or emoji support.
- **Almost no setup required** — install it, launch it, and start using it right away.
- **Quick access** — open it with the `Ctrl+Alt+E` hotkey or from the system tray.
- **Unobtrusive interface** — a compact semi-transparent window with a muted dark background stays out of your way and looks clean over other windows.
- **Your own emojis inside the app** — you can add custom emojis, organize them, and keep your favorites close at hand.

### Features

- **One-click insertion** — clicking an emoji copies it to the clipboard and tries to paste it into the active input field.
- **Hotkey** — `Ctrl+Alt+E` for quick access.
- **Auto-show** — the window can appear automatically when a text field gets focus (can be toggled from the tray menu).
- **Tray integration** — a system tray icon lets you show/hide the window with a double-click and access settings from the tray menu.
- **Search and categories** — convenient name search (en/ru) and categories: Recent, Round, Nature/Food, Symbols, Added.
- **Recent emojis** — your recently used emojis are saved for quick reuse.
- **Custom emojis** — add your own emojis directly in the app using the `+` button.
- **Emoji management** — move emojis between categories by dragging, and remove unwanted ones from the context menu.
- **Comfortable window** — borderless interface, drag to move, resize support, saved position and settings.
- **Autostart** — optionally launch with Windows.

### Screenshots

Semi-transparent window; you can resize it to your preference.

![Eptal emoji — semi-transparent window](images/screenshot.png)

![Eptal emoji — adjustable window size](images/screenshot-2.png)

App settings are available by right-clicking the Eptal emoji icon in the system tray.

![Tray menu settings](images/settings.png)

### Requirements

- Windows
- Python 3.10+ (for running from source)

Dependencies:
- PyQt6
- emoji
- keyboard
- pyperclip
- uiautomation

### Install and Run from Source

```bash
pip install -r requirements.txt
pythonw eptal_emoji.py
```

### Build a Standalone `.exe` (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --icon=eptal_emoji.ico --name EptalEmoji eptal_emoji.py
```

The output file will appear in `dist/EptalEmoji.exe`. You can use `Start.bat` to launch it.

### Usage

- `Ctrl+Alt+E` — show the emoji picker window.
- Click an emoji — insert it into the active field (when possible).
- `+` button — add your own emojis.
- Drag an emoji onto a tab — move it between categories.
- Right-click an emoji — delete/hide it.
- Double-click the tray icon — show/hide the window.

### Notes

- Auto-show on focus and auto-paste depend on the target application and UI Automation availability.
- Global hotkeys/hooks (`keyboard`) may require running with elevated privileges in some cases.
- History, settings, added and hidden emojis are stored locally in the user profile.

### License

This project is distributed under the MIT License. See [LICENSE](LICENSE).
