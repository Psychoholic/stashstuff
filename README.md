# Stash Duplicate Management Scripts

A collection of Python scripts for managing duplicate scenes in [Stash](https://github.com/stashapp/stash) media server using the GraphQL API.

## Scripts

### 🔄 find-phash-dupes.py
Intelligent duplicate scene detection and merging using Stash's built-in perceptual hash (phash) duplicate detection.

**Features:**
- Uses Stash's `findDuplicateScenes` GraphQL query for accurate detection
- Configurable similarity tolerance (distance parameter)
- Smart scene merging that preserves the best metadata and MKV files
- Batch processing to avoid overwhelming your system
- Automatic MKV file prioritization as primary
- Comprehensive scoring system for metadata and file quality

### 📁 update-dupes.py
Scene file management for scenarios with multiple files per scene.

**Features:**
- Finds scenes with multiple video files
- Sets MKV files as primary over MP4 files
- Batch processing with user confirmation
- Safe file deletion with error handling

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/stashstuff.git
   cd stashstuff
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp env.example .env
   # Edit .env with your Stash server details
   ```

## Configuration

### Environment Variables

Copy `env.example` to `.env` and configure:

```bash
# Stash server URL (include protocol and port)
STASH_URL=http://localhost:9999

# Your Stash API key (generate this in Stash Settings > Security)
STASH_API_KEY=your_api_key_here
```

### Script Configuration

Both scripts have configurable parameters at the top:

**find-phash-dupes.py:**
- `PHASH_DISTANCE`: Similarity tolerance (0=exact, 4=high, 8=medium, 16=low)
- `BATCH_SIZE`: Number of duplicate groups to process per run
- `DELAY_BETWEEN_MERGES`: Seconds to wait between operations

## Usage

### Finding and Merging Duplicates

```bash
python find-phash-dupes.py
```

**Distance Settings:**
- `0` - Exact matches only (fastest, no false positives)
- `4` - High accuracy (recommended, very few false positives)
- `8` - Medium accuracy (good balance)
- `16` - Low accuracy (more matches, may include false positives)

### Managing Multiple Files

```bash
python update-dupes.py
```

This script will:
1. Find all scenes with multiple video files
2. Set MKV files as primary
3. Delete MP4 files after confirmation

## How It Works

### Duplicate Detection Process

1. **Phash Generation**: Stash generates perceptual hashes from video frames
2. **Similarity Search**: Finds scenes within specified distance threshold
3. **Smart Analysis**: Evaluates scenes based on:
   - **Metadata Quality**: Rating, title, studio, performers, scene markers
   - **File Quality**: Size, bitrate, codec (HEVC preferred)
   - **Format Preference**: MKV strongly preferred over MP4

4. **Intelligent Merging**: 
   - Chooses scene with best file (MKV + HEVC preferred) as destination
   - Merges all duplicate scenes into the destination
   - Sets MKV file as primary
   - Preserves all metadata and files

### Scoring System

**Metadata Scoring:**
- Rating: +100 points
- Title: +50 points  
- Studio: +25 points
- Performers: +25 points
- Scene Markers: +10 points each

**File Scoring:**
- MKV format: +1000 points
- HEVC codec: +500 points
- File size and bitrate: normalized points

## Safety Features

- **Batch Processing**: Processes manageable chunks to avoid system overload
- **Preview Mode**: Shows what will be processed before execution
- **Error Handling**: Comprehensive error checking and reporting
- **Gentle Operation**: Configurable delays between operations
- **Detailed Logging**: Clear progress indicators and results

## Requirements

- Python 3.7+
- Stash media server with API access
- Generated perceptual hashes (phashes) in Stash

## Generating Perceptual Hashes

Before using the duplicate detection script, ensure your scenes have phashes:

1. **During Scan**: Enable "Generate perceptual hashes" in scan settings
2. **Manual Generation**: Use the Generate task in Stash Settings > Tasks
3. **Individual Scenes**: Use "Generate..." option on selected scenes

## API Permissions

Your Stash API key needs permissions for:
- Reading scene data
- Merging scenes (`sceneMerge` mutation)
- Updating scene metadata
- Setting primary files

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve these scripts.

## License

This project is open source. Please respect the Stash project's licensing terms.

## Disclaimer

**Always backup your Stash database before running these scripts.** While designed to be safe, these scripts modify your Stash database and file associations. Test on a small subset first.

## Support

For issues related to:
- **Stash itself**: Visit the [Stash GitHub repository](https://github.com/stashapp/stash)
- **These scripts**: Open an issue in this repository
- **General help**: Join the Stash Discord community 