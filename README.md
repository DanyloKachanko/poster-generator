# Poster Generator

A web application for generating posters using Leonardo AI API.

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Next.js 14 with App Router + Tailwind CSS
- **AI**: Leonardo AI for image generation

## Project Structure

```
poster-generator/
├── backend/
│   ├── main.py              # FastAPI app with endpoints
│   ├── leonardo.py          # Leonardo AI API wrapper class
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx         # Main generator page
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── StyleSelector.tsx
│   │   ├── PresetSelector.tsx
│   │   ├── PromptInput.tsx
│   │   ├── GenerateButton.tsx
│   │   └── ImageGallery.tsx
│   ├── lib/
│   │   └── api.ts           # API client functions
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── Dockerfile
├── docker-compose.yml
├── .env                     # All environment variables here
├── .env.example
└── README.md
```

## Quick Start with Docker

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env and add your LEONARDO_API_KEY

# 2. Run
docker-compose up --build

# 3. Open http://localhost:3000
```

## Environment Variables

All environment variables are in the root `.env` file:

```
LEONARDO_API_KEY=your_api_key_here
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Manual Setup (without Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
# Make sure .env is configured in root directory
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
# Set NEXT_PUBLIC_API_URL in root .env
npm run dev
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/styles` | Get all available style presets |
| POST | `/generate` | Start image generation |
| GET | `/generation/{id}` | Check generation status |

## Available Styles

- **Japanese**: Mountain Landscape, Ocean Waves, Cherry Blossom, Zen Garden
- **Botanical**: Single Leaf, Fern Fronds, Eucalyptus
- **Abstract**: Geometric Shapes, Arch Shapes, Overlapping Circles
- **Celestial**: Moon Phases, Starry Night, Sun Rays

## Image Sizes

Default: 1200 x 1500 px (4:5 ratio) - optimized for poster printing

Supported aspect ratios:
- 4:5 (for 8x10, 16x20 inch posters)
- 2:3 (for 12x18, 24x36 inch posters)
- 3:4 (for 12x16, 18x24 inch posters)

## Usage

1. Open http://localhost:3000
2. Select a style (Japanese, Botanical, Abstract, or Celestial)
3. Choose a preset or switch to custom prompt mode
4. Set the number of images (1-4)
5. Click Generate
6. Download your generated posters

## Notes

- Generated image URLs expire after some time
- Rate limits apply to the Leonardo AI API
- This is an internal tool designed for simplicity
