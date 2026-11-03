# Telegram Bot

- Multipurpose Telegram bot built with `python-telegram-bot`
- 38 commands grouped in 11 categories: weather, text, converters, security, maths, media, finance, networking, entertainment, games and productivity
- Interactive help menu with inline buttons
- Error handling with styled terminal messages and friendly replies
- Free public APIs only (no keys required except the optional TMDB key)

<img src="public/cover.png" alt="Telegram Bot Cover" width="400">

## Requirements

- Python 3.10 or newer
- `pip` (Python package manager)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Installation

1. Clone the repository or download the project files.

```bash
git clone git@github.com:hectorOliSan/telegram-bot.git
```

2. Create a virtual environment:

```bash
python -m venv .venv
```

3. Activate the virtual environment:

```bash
source .venv/bin/activate     # Linux/macOS
.venv\Scripts\activate        # Windows
```

4. Install the dependencies:

```bash
pip install -r requirements.txt
```

5. Create the `.env` file from `.env.example`:

```bash
TELEGRAM_BOT_TOKEN=123456:ABC...
TMDB_API_KEY=              # Optional: required by /film, TMDB series in /series (TVmaze without key)
TIMEZONE=Atlantic/Canary   # Optional: default timezone for /now and /ephemeris
```

## Project Structure

```
telegram-bot/
├── commands/
│   ├── conversion.py    # Currency and unit converter
│   ├── finance.py       # Crypto, currencies and market indices
│   ├── fun.py           # Pokémon, Wikipedia, jokes, quotes, films, series, ephemeris
│   ├── games.py         # Coin, random number, dice
│   ├── maths.py         # Calculator, primes, Fibonacci, percentages
│   ├── media.py         # QR, colors, palettes, avatars
│   ├── network.py       # Ping, WHOIS, HTTP headers
│   ├── productivity.py  # Timer and current time
│   ├── security.py      # Passwords, hashes, Base64, IDs
│   ├── text.py          # Word/character counters, Lorem Ipsum
│   └── weather.py       # Current weather
├── main.py              # Bot entry point, command registry, start and help
├── decorators.py        # Styled printing and error-handling utilities
├── utils.py             # HTTP helpers, argument parsing and formatting
├── requirements.txt     # Project dependencies
├── .env.example
├── .gitignore
└── README.md
```

### Dependencies

- `python-telegram-bot[job-queue]`: Telegram Bot API wrapper and job queue for timers
- `httpx`: Async HTTP client for public APIs
- `pillow`: Image generation (colors, palettes, avatars, sprites)
- `qrcode`: QR code generation
- `pint`: Unit conversion
- `python-whois`: WHOIS lookups
- `python-dotenv`: Loads environment variables from `.env`
- `rich`: Terminal styling and colors
- `tzdata`: Timezone database (needed on Windows)

## Usage

```bash
python main.py
```

## Commands

| Category        | Command                                     | Description                                                    |
| --------------- | ------------------------------------------- | -------------------------------------------------------------- |
| Weather         | `/weather [city]`                           | Current weather; without city asks for the user's location     |
| Text            | `/count_words <text>`                       | Word count (also `/count-words`)                               |
| Text            | `/count_letter <text>`                      | Characters with and without spaces (also `/count-letter`)      |
| Text            | `/lorem <words>`                            | Lorem Ipsum text (also `/loremipsum`)                          |
| Converters      | `/conversion <amount> <from> <to>`          | Currencies (`EUR a USD`), units (`km a mi`), time (`horas a min`) |
| Security        | `/password <length>`                        | Secure random password                                         |
| Security        | `/hash <text>`                              | MD5, SHA-256 and SHA-512 hashes                                |
| Security        | `/base64_encode <text>`                     | Base64 encoding                                                |
| Security        | `/base64_decode <code>`                     | Base64 decoding                                                |
| Security        | `/id`                                       | User and chat Telegram IDs                                     |
| Maths           | `/calculate <expression>`                   | Safe math evaluator, e.g. `2*(5+3)^2`                          |
| Maths           | `/prime <number>`                           | Primality test                                                 |
| Maths           | `/fibonacci <number>`                       | n-th Fibonacci number (also `/fibbonacci`)                     |
| Maths           | `/percent <part> <total>`                   | Percentage of a part over a total                              |
| Media           | `/qr <text_or_url>`                         | QR code image                                                  |
| Media           | `/color`                                    | Random hex color with preview                                  |
| Media           | `/palette [3-5]`                            | Random palette with preview                                    |
| Media           | `/avatar <seed>`                            | GitHub-style identicon from a seed                             |
| Finance         | `/crypto <symbol>`                          | Price, 24h change, volume and market cap                       |
| Finance         | `/currency <symbol>`                        | Exchange rates and daily change (also `/moneda`, accepts `€`, `$`, `euro`...) |
| Finance         | `/financial_market`                         | IBEX 35, S&P 500, Nasdaq, Dow Jones and top cryptos (also `/financial-market`) |
| Networking      | `/ping <domain>`                            | TCP latency and availability                                   |
| Networking      | `/whois <domain>`                           | Domain registration data                                       |
| Networking      | `/headers <url>`                            | HTTP response headers                                          |
| Entertainment   | `/pokemon`                                  | Random Pokémon with stats and pixel-art sprite                 |
| Entertainment   | `/wiki`                                     | Random Spanish Wikipedia article                               |
| Entertainment   | `/joke`                                     | Random joke in Spanish                                         |
| Entertainment   | `/quote`                                    | Random famous quote                                            |
| Entertainment   | `/film`                                     | Random movie with synopsis, rating and poster (TMDB key)       |
| Entertainment   | `/series`                                   | Random TV series with synopsis, rating and poster              |
| Entertainment   | `/ephemeris`                                | Historical events on this day                                  |
| Games           | `/coin`                                     | Heads or tails                                                 |
| Games           | `/number [min] [max]`                       | Random number, 0-100 by default (also `/num`)                  |
| Games           | `/die [sides]` or `/d<X>`                   | Dice roll, 6 sides by default                                  |
| Productivity    | `/timer <seconds>`                          | Countdown with alert (accepts `5m`, `1h30m`)                   |
| Productivity    | `/now [timezone]`                           | Time, date, timezone and day of the year                       |
| System          | `/start`                                    | Welcome message and feature summary                            |
| System          | `/help`                                     | Interactive help menu by category                              |

Telegram only allows lowercase letters, digits and underscores in command names, so hyphenated aliases (`/count-words`, `/financial-market`) work when typed but the menu shows the underscore version.

## Data Sources

- [Open-Meteo](https://open-meteo.com/): weather and geocoding
- [Frankfurter](https://frankfurter.dev/): ECB exchange rates
- [CoinGecko](https://www.coingecko.com/en/api): crypto prices
- Yahoo Finance: market indices
- [PokéAPI](https://pokeapi.co/), [Wikipedia](https://es.wikipedia.org/), [JokeAPI](https://jokeapi.dev/), [ZenQuotes](https://zenquotes.io/), [TMDB](https://www.themoviedb.org/) / [TVmaze](https://www.tvmaze.com/api), [Wikimedia Feed](https://api.wikimedia.org/)

---

Developed by Héctor Olivares Sánchez.

<a href="https://www.themoviedb.org/"><img src="https://www.themoviedb.org/assets/v4/logos/v2/blue_short-8e7b30f73a4020692ccca9c88bafe5dcb6f8a62a4c6bc55cd9ba82bb2cd95f6c.svg" alt="TMDB logo" width="120"></a>

This product uses the TMDB API but is not endorsed or certified by TMDB.
