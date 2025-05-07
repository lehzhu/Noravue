# Noravue

A screenshot analysis and triage system that helps you manage, organize, and extract information from your screenshots. This tool uses OCR (Optical Character Recognition) to extract text from images, and provides a web interface for easy management.

![Demo](./screenshots/demo.gif)

## Features

- Upload and manage screenshots through an intuitive web interface
- Automatic text extraction using OCR
- Tagging and organization system
- Search functionality based on extracted text
- Session-based storage for privacy
- Batch processing for handling multiple uploads

## Prerequisites

- Python 3.11 or higher
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) - Required for text extraction
- PostgreSQL (optional, SQLite works for local development)

### Installing Tesseract OCR

#### macOS
```bash
brew install tesseract
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install tesseract-ocr
```

#### Windows
Download and install the [Tesseract installer](https://github.com/UB-Mannheim/tesseract/wiki)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/lehzhu/Noravue.git
cd Noravue
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

4. Create necessary directories:
```bash
mkdir -p screenshots documents temp_uploads
```

## Configuration

The application uses environment variables for configuration. Create a `.env` file in the project root with the following options:

```
# Database configuration
DATABASE_URL=sqlite:///instance/screenshots.db
# For PostgreSQL: DATABASE_URL=postgresql://username:password@localhost/dbname

# Flask configuration
FLASK_APP=main.py
FLASK_ENV=development
FLASK_SECRET_KEY=your_secret_key_here

# Storage paths
SCREENSHOTS_FOLDER=./screenshots
DOCUMENTS_FOLDER=./documents

# Optional: OpenAI API integration
OPENAI_API_KEY=your_openai_api_key
```

## Usage

1. Start the application:
```bash
flask run
```
Or:
```bash
python main.py
```

2. Open a web browser and navigate to:
```
http://localhost:5000
```

3. Upload screenshots through the web interface.

4. View, tag, and organize your screenshots.

## Privacy and Data Security

Noravue is designed with privacy in mind:

- **Session-based storage**: All uploaded screenshots and data are managed within your browser session
- **Local processing**: OCR and image analysis happens locally on your machine
- **No cloud storage**: By default, all files remain on your local system
- **Automatic cleanup**: Session data is automatically removed when your browser session ends
- **Self-hosted**: You control your own instance and data

## Development Setup

For development:

1. Install development dependencies:
```bash
pip install -e ".[dev]"
```

2. Setup pre-commit hooks:
```bash
pre-commit install
```

3. Run tests:
```bash
pytest
```

4. For database migrations (when using SQLAlchemy with PostgreSQL):
```bash
flask db init    # First time only
flask db migrate -m "Migration message"
flask db upgrade
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Generating the Demo GIF

To create a demo GIF for documentation:

1. Record a short video demonstrating the application's features
2. Use ffmpeg to convert the video to an optimized GIF:

```bash
ffmpeg -i input_video.mp4 -vf "fps=10,scale=800:-1:flags=lanczos" -c:v gif -f gif ./screenshots/demo.gif
```

This command:
- Sets the framerate to 10 fps
- Scales the width to 800px while maintaining aspect ratio
- Uses high-quality lanczos scaling algorithm
- Outputs an optimized GIF file

