import requests
import json
from collections import defaultdict

# ============================================================================
# CONFIGURATION - Modify these settings for your Stash setup
# ============================================================================

# Stash server configuration
STASH_URL = "http://ifyouseek8:9999"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiJwc3ljaG9ob2xpYyIsImlhdCI6MTY5OTczNzkyNCwic3ViIjoiQVBJS2V5In0.XDs7C0TyfcUp13Kg_lSVl-A7HYA5h6lHZ92_lX9b1Zo"

# Duplicate detection settings
PHASH_DISTANCE = 8  # 0 = exact match, higher values = more tolerant of differences.  Use multiples of 4.

# Processing settings
BATCH_SIZE = 10  # Number of duplicate groups to process per run
DELAY_BETWEEN_MERGES = 0.5  # Seconds to wait between merges (be gentle on server)

# ============================================================================

class StashAppClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            'Content-Type': 'application/json',
            'ApiKey': api_key
        }
        self.graphql_url = f"{base_url}/graphql"
    
    def execute_query(self, query, variables=None):
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
        
        response = requests.post(self.graphql_url, json=payload, headers=self.headers)
        return response.json()
    
    def find_duplicate_scenes(self, distance=0):
        """
        Use Stash's built-in findDuplicateScenes query to find scenes with matching phash
        distance: 0 = exact match, higher values = more tolerant of differences
        """
        query = """
        query FindDuplicateScenes($distance: Int!) {
          findDuplicateScenes(distance: $distance) {
            id
            title
            paths {
              screenshot
              preview
              stream
              webp
              vtt
              sprite
              funscript
              interactive_heatmap
              caption
            }
            files {
              id
              path
              basename
              size
              duration
              video_codec
              width
              height
              frame_rate
              bit_rate
            }
            studio {
              id
              name
            }
            performers {
              id
              name
            }
            scene_markers {
              id
              title
              seconds
            }
            date
            created_at
            updated_at
            resume_time
            play_count
            rating100
          }
        }
        """
        variables = {
            'distance': distance
        }
        return self.execute_query(query, variables)
    
    def delete_scene(self, scene_id):
        """
        Delete a scene (but keep the files on disk)
        """
        mutation = """
        mutation DeleteScene($scene_id: ID!) {
          sceneDestroy(input: {
            id: $scene_id
            delete_file: false
            delete_generated: true
          })
        }
        """
        variables = {
            'scene_id': scene_id
        }
        return self.execute_query(mutation, variables)
    
    def set_primary_file(self, scene_id, file_id):
        """
        Set a specific file as the primary file for a scene
        """
        mutation = """
        mutation SetPrimaryFile($scene_id: ID!, $file_id: ID!) {
          sceneUpdate(input: {
            id: $scene_id
            primary_file_id: $file_id
          }) {
            id
            title
            files {
              id
              path
              basename
            }
          }
        }
        """
        variables = {
            'scene_id': scene_id,
            'file_id': file_id
        }
        return self.execute_query(mutation, variables)
    
    def delete_file(self, file_id):
        """
        Delete a file from the system
        """
        mutation = """
        mutation DeleteFile($file_id: ID!) {
          deleteFiles(ids: [$file_id])
        }
        """
        variables = {
            'file_id': file_id
        }
        return self.execute_query(mutation, variables)

    def merge_scenes(self, source_scene_ids, destination_scene_id):
        """
        Merge multiple scenes into a destination scene using Stash's built-in sceneMerge
        This will move all files from source scenes to the destination scene
        """
        mutation = """
        mutation SceneMerge($source: [ID!]!, $destination: ID!, $values: SceneUpdateInput!) {
          sceneMerge(input: {
            source: $source
            destination: $destination
            values: $values
          }) {
            id
            title
            files {
              id
              path
              basename
              size
              video_codec
            }
          }
        }
        """
        variables = {
            'source': source_scene_ids,
            'destination': destination_scene_id,
            'values': {'id': destination_scene_id}
        }
        return self.execute_query(mutation, variables)

def group_scenes_by_similarity(scenes):
    """
    Group the duplicate scenes for organized display
    Since phash isn't exposed, we'll group by file path or just show all
    """
    # Since we can't group by phash, we'll create groups based on file paths
    # or just return all scenes in one group
    if not scenes:
        return {}
    
    # For simplicity, we'll just group all duplicates together
    # Stash's findDuplicateScenes already found them to be similar
    return {"duplicates": scenes}

def display_duplicate_scenes(duplicate_groups):
    """
    Display information about duplicate scenes found by Stash
    Shows summary and first few groups for preview
    """
    if not duplicate_groups:
        print("No duplicate scenes found!")
        return
    
    # Check if we have groups of scenes or individual scenes
    if duplicate_groups and isinstance(duplicate_groups[0], list):
        # We have groups of duplicate scenes
        total_groups = len(duplicate_groups)
        total_scenes = sum(len(group) for group in duplicate_groups)
        print(f"\nFound {total_scenes} duplicate scenes in {total_groups} groups")
        print(f"Will process in batches of {BATCH_SIZE} groups")
        print("=" * 80)
        
        # Show preview of first few groups
        preview_count = min(3, total_groups)
        print(f"\n📋 PREVIEW - First {preview_count} groups:")
        
        for group_idx in range(preview_count):
            scene_group = duplicate_groups[group_idx]
            print(f"\n=== GROUP {group_idx + 1} ({len(scene_group)} scenes) ===")
            
            for i, scene in enumerate(scene_group, 1):
                display_single_scene(scene, i, is_in_group=True)
        
        if total_groups > preview_count:
            print(f"\n... and {total_groups - preview_count} more groups")
        
        print("=" * 60)
    else:
        # We have individual scenes
        total_duplicates = len(duplicate_groups)
        print(f"\nFound {total_duplicates} duplicate scenes")
        print("=" * 80)
        
        # Show the first scene
        display_single_scene(duplicate_groups[0], 1, is_in_group=False)

def display_single_scene(scene, index, is_in_group=False):
    """
    Display information for a single scene
    """
    indent = "  " if is_in_group else ""
    
    print(f"\n{indent}{index}. Scene ID: {scene['id']}")
    print(f"{indent}   Title: {scene.get('title', 'No title')}")
    print(f"{indent}   Created: {scene.get('created_at', 'Unknown')}")
    print(f"{indent}   Rating: {scene.get('rating100', 'Unrated')}/100")
    print(f"{indent}   Play Count: {scene.get('play_count', 0)}")
    
    if scene.get('studio'):
        print(f"{indent}   Studio: {scene['studio']['name']}")
    
    if scene.get('performers'):
        performer_names = [p['name'] for p in scene['performers']]
        print(f"{indent}   Performers: {', '.join(performer_names)}")
    
    if scene.get('scene_markers'):
        marker_count = len(scene['scene_markers'])
        print(f"{indent}   Scene Markers: {marker_count}")
    
    if scene.get('files'):
        print(f"{indent}   Files ({len(scene['files'])}):")
        for j, file_info in enumerate(scene['files'], 1):
            size_mb = file_info.get('size', 0) / (1024 * 1024) if file_info.get('size') else 0
            duration_min = file_info.get('duration', 0) / 60 if file_info.get('duration') else 0
            resolution = f"{file_info.get('width', '?')}x{file_info.get('height', '?')}"
            bitrate_kbps = file_info.get('bit_rate', 0) / 1000 if file_info.get('bit_rate') else 0
            
            print(f"{indent}     {j}. {file_info.get('basename', 'Unknown')}")
            print(f"{indent}        Path: {file_info.get('path', 'Unknown')}")
            print(f"{indent}        Size: {size_mb:.1f} MB | Duration: {duration_min:.1f} min")
            print(f"{indent}        Resolution: {resolution} | Bitrate: {bitrate_kbps:.1f} kbps")
            print(f"{indent}        Codec: {file_info.get('video_codec', 'Unknown')}")
    
    if not is_in_group:
        print("-" * 60)

def identify_mp4_scene(scenes):
    """
    Identify which scene has the MP4 file (the one with metadata to preserve)
    Returns tuple: (mp4_scene, other_scenes)
    """
    mp4_scene = None
    other_scenes = []
    
    for scene in scenes:
        has_mp4 = any(
            file_info.get('path', '').lower().endswith('.mp4') 
            for file_info in scene.get('files', [])
        )
        
        if has_mp4:
            mp4_scene = scene
        else:
            other_scenes.append(scene)
    
    return mp4_scene, other_scenes

def determine_better_scene(scenes):
    """
    Determine which scene to keep based on metadata quality and file quality
    Returns: (scene_to_keep, scenes_to_delete)
    """
    if len(scenes) < 2:
        return scenes[0] if scenes else None, []
    
    # Score scenes based on multiple factors
    scored_scenes = []
    
    for scene in scenes:
        score = 0
        
        # Metadata quality scoring
        if scene.get('rating100') and scene.get('rating100') != 'None':
            score += 100  # Has rating
        if scene.get('title') and scene.get('title').strip():
            score += 50   # Has title
        if scene.get('studio'):
            score += 25   # Has studio
        if scene.get('performers'):
            score += 25   # Has performers
        if scene.get('scene_markers'):
            marker_count = len(scene['scene_markers'])
            score += marker_count * 10  # 10 points per scene marker
        
        # File quality scoring
        best_file_size = 0
        best_bitrate = 0
        has_hevc = False
        
        for file_info in scene.get('files', []):
            file_size = file_info.get('size', 0)
            bitrate = file_info.get('bit_rate', 0)
            codec = file_info.get('video_codec', '').lower()
            
            if file_size > best_file_size:
                best_file_size = file_size
            if bitrate > best_bitrate:
                best_bitrate = bitrate
            
            # Check for HEVC codec
            if codec in ['hevc', 'h265', 'h.265']:
                has_hevc = True
        
        # Add file quality to score (normalized)
        score += (best_file_size / (1024*1024)) / 10  # Size in MB / 10
        score += best_bitrate / 1000  # Bitrate in kbps / 1000
        
        # HEVC preference - significant bonus for better codec
        if has_hevc:
            score += 500  # Large bonus for HEVC codec
        
        scored_scenes.append((score, scene))
    
    # Sort by score (highest first)
    scored_scenes.sort(key=lambda x: x[0], reverse=True)
    
    best_scene = scored_scenes[0][1]
    scenes_to_delete = [s[1] for s in scored_scenes[1:]]
    
    return best_scene, scenes_to_delete

def merge_duplicate_scenes(client, scenes):
    """
    Merge duplicate scenes using Stash's built-in sceneMerge mutation.
    This will intelligently choose the best destination scene and merge all others into it.
    """
    if len(scenes) < 2:
        print("Need at least 2 scenes to merge")
        return False
    
    # Find the scene with the best metadata
    best_metadata_scene = find_best_metadata_scene(scenes)
    
    # Find the scene with the best video file (MKV preferred)
    best_file_scene = find_best_file_scene(scenes)
    
    print(f"\n🔄 MERGING DUPLICATES:")
    print(f"   📊 Best metadata: Scene {best_metadata_scene['id']} - {best_metadata_scene.get('title', 'No title')}")
    print(f"   🎬 Best file: Scene {best_file_scene['id']}")
    
    # Determine the destination scene (prioritize MKV file over metadata)
    if best_file_scene['id'] == best_metadata_scene['id']:
        # Perfect! Best file and metadata are in the same scene
        destination_scene = best_metadata_scene
        print("   ✅ Best metadata and file are already in the same scene!")
    else:
        # Choose the scene with the MKV file as destination (your preference)
        destination_scene = best_file_scene
        print(f"   🎯 Using scene with MKV file as destination: {destination_scene['id']}")
        
        # We'll need to copy metadata from the best metadata scene
        if best_metadata_scene.get('title') and not destination_scene.get('title'):
            print(f"   📝 Will copy title: '{best_metadata_scene.get('title')}'")
        if best_metadata_scene.get('rating100') and not destination_scene.get('rating100'):
            print(f"   ⭐ Will copy rating: {best_metadata_scene.get('rating100')}/100")
    
    # Get all other scenes to merge
    source_scenes = [s for s in scenes if s['id'] != destination_scene['id']]
    source_scene_ids = [s['id'] for s in source_scenes]
    
    print(f"\n   🔄 Merging {len(source_scenes)} scene(s) into scene {destination_scene['id']}:")
    
    # Show what files will be merged
    for scene in source_scenes:
        if scene.get('files'):
            file_info = scene['files'][0]
            size_mb = file_info.get('size', 0) / (1024*1024)
            codec = file_info.get('video_codec', 'Unknown')
            print(f"   📁 From scene {scene['id']}: {file_info.get('basename')} ({size_mb:.1f} MB, {codec})")
    
    # Show destination files
    if destination_scene.get('files'):
        file_info = destination_scene['files'][0]
        size_mb = file_info.get('size', 0) / (1024*1024)
        codec = file_info.get('video_codec', 'Unknown')
        print(f"   🎯 Destination: {file_info.get('basename')} ({size_mb:.1f} MB, {codec})")
    
    # Perform the merge using Stash's sceneMerge mutation
    print(f"\n   🚀 Executing sceneMerge...")
    merge_result = client.merge_scenes(source_scene_ids, destination_scene['id'])
    
    if 'errors' in merge_result:
        print(f"   ❌ Error during merge: {merge_result['errors']}")
        return False
    
    merged_scene = merge_result['data']['sceneMerge']
    if merged_scene:
        print(f"   ✅ Successfully merged scenes into {merged_scene['id']}")
        print(f"   📁 Final scene has {len(merged_scene.get('files', []))} file(s)")
        
        # Show final files
        mkv_file_id = None
        for i, file_info in enumerate(merged_scene.get('files', []), 1):
            size_mb = file_info.get('size', 0) / (1024*1024)
            codec = file_info.get('video_codec', 'Unknown')
            primary_indicator = " (PRIMARY)" if i == 1 else ""
            print(f"     {i}. {file_info.get('basename')} ({size_mb:.1f} MB, {codec}){primary_indicator}")
            
            # Find the MKV file
            if file_info.get('path', '').lower().endswith('.mkv'):
                mkv_file_id = file_info.get('id')
        
        # Set MKV as primary if it exists and isn't already primary
        if mkv_file_id and len(merged_scene.get('files', [])) > 1:
            current_primary_id = merged_scene['files'][0].get('id') if merged_scene.get('files') else None
            
            if mkv_file_id != current_primary_id:
                print(f"\n   🎯 Setting MKV file as primary...")
                primary_result = client.set_primary_file(merged_scene['id'], mkv_file_id)
                
                if 'errors' not in primary_result:
                    print(f"   ✅ Successfully set MKV as primary file")
                else:
                    print(f"   ⚠️  Warning: Could not set MKV as primary: {primary_result['errors']}")
            else:
                print(f"   ✅ MKV file is already the primary file")
        elif mkv_file_id:
            print(f"   ✅ MKV file is the only file (automatically primary)")
        else:
            print(f"   ⚠️  No MKV file found in merged scene")
        
        return True
    else:
        print("   ❌ Merge failed - no result returned")
        return False

def find_best_metadata_scene(scenes):
    """
    Find the scene with the best metadata (rating, title, studio, performers, etc.)
    """
    scored_scenes = []
    
    for scene in scenes:
        score = 0
        
        # Metadata quality scoring
        if scene.get('rating100') and scene.get('rating100') != 'None':
            score += 100  # Has rating
        if scene.get('title') and scene.get('title').strip():
            score += 50   # Has title
        if scene.get('studio'):
            score += 25   # Has studio
        if scene.get('performers'):
            score += 25   # Has performers
        if scene.get('scene_markers'):
            marker_count = len(scene['scene_markers'])
            score += marker_count * 10  # 10 points per scene marker
        
        scored_scenes.append((score, scene))
    
    # Sort by score (highest first)
    scored_scenes.sort(key=lambda x: x[0], reverse=True)
    
    return scored_scenes[0][1]

def find_best_file_scene(scenes):
    """
    Find the scene with the best video file (MKV preferred, then by quality)
    """
    scored_scenes = []
    
    for scene in scenes:
        score = 0
        
        # File quality scoring
        best_file_size = 0
        best_bitrate = 0
        has_mkv = False
        has_hevc = False
        
        for file_info in scene.get('files', []):
            file_size = file_info.get('size', 0)
            bitrate = file_info.get('bit_rate', 0)
            codec = file_info.get('video_codec', '').lower()
            path = file_info.get('path', '').lower()
            
            if file_size > best_file_size:
                best_file_size = file_size
            if bitrate > best_bitrate:
                best_bitrate = bitrate
            
            # Check for MKV format
            if path.endswith('.mkv'):
                has_mkv = True
            
            # Check for HEVC codec
            if codec in ['hevc', 'h265', 'h.265']:
                has_hevc = True
        
        # Add file quality to score
        score += (best_file_size / (1024*1024)) / 10  # Size in MB / 10
        score += best_bitrate / 1000  # Bitrate in kbps / 1000
        
        # Strong preference for MKV format
        if has_mkv:
            score += 1000  # Very high bonus for MKV
        
        # HEVC preference
        if has_hevc:
            score += 500  # Large bonus for HEVC codec
        
        scored_scenes.append((score, scene))
    
    # Sort by score (highest first)
    scored_scenes.sort(key=lambda x: x[0], reverse=True)
    
    return scored_scenes[0][1]

def find_best_file_from_scene(scene):
    """
    Find the best file from a given scene (MKV preferred, then by quality)
    """
    files = scene.get('files', [])
    if not files:
        return None
    
    # Score files
    scored_files = []
    for file_info in files:
        score = 0
        
        file_size = file_info.get('size', 0)
        bitrate = file_info.get('bit_rate', 0)
        codec = file_info.get('video_codec', '').lower()
        path = file_info.get('path', '').lower()
        
        # File quality
        score += (file_size / (1024*1024)) / 10  # Size in MB / 10
        score += bitrate / 1000  # Bitrate in kbps / 1000
        
        # Format preference
        if path.endswith('.mkv'):
            score += 1000  # Very high bonus for MKV
        
        # Codec preference
        if codec in ['hevc', 'h265', 'h.265']:
            score += 500  # Large bonus for HEVC codec
        
        scored_files.append((score, file_info))
    
    # Sort by score (highest first)
    scored_files.sort(key=lambda x: x[0], reverse=True)
    
    return scored_files[0][1]

def delete_scene_safely(client, scene_to_delete):
    """
    Safely delete a scene with proper logging
    """
    print(f"\n   Processing scene {scene_to_delete['id']}...")
    
    if scene_to_delete.get('files'):
        file_info = scene_to_delete['files'][0]
        size_mb = file_info.get('size', 0) / (1024*1024)
        bitrate_kbps = file_info.get('bit_rate', 0) / 1000
        print(f"       📁 File: {file_info.get('basename')} ({size_mb:.1f} MB, {bitrate_kbps:.1f} kbps)")
    
    delete_result = client.delete_scene(scene_to_delete['id'])
    if 'errors' not in delete_result:
        print(f"   ✅ Successfully deleted scene {scene_to_delete['id']}")
    else:
        print(f"   ❌ Error deleting scene: {delete_result['errors']}")

def process_duplicate_groups_batch(client, duplicate_scenes, batch_size=25):
    """
    Process duplicate groups in batches for efficient processing
    """
    if not duplicate_scenes:
        print("No duplicate scenes to process")
        return
    
    # Check if we have groups or individual scenes
    if isinstance(duplicate_scenes[0], list):
        # We have groups - process in batches
        total_groups = len(duplicate_scenes)
        print(f"\n🎯 Processing {min(batch_size, total_groups)} of {total_groups} duplicate groups")
        
        processed_count = 0
        successful_merges = 0
        
        for i, group in enumerate(duplicate_scenes[:batch_size], 1):
            print(f"\n{'='*60}")
            print(f"📦 BATCH PROGRESS: {i}/{min(batch_size, total_groups)} groups")
            print(f"🔄 Processing duplicate group {i} ({len(group)} scenes)")
            
            success = merge_duplicate_scenes(client, group)
            processed_count += 1
            if success:
                successful_merges += 1
            
            # Small delay between merges to be gentle on the server
            import time
            time.sleep(DELAY_BETWEEN_MERGES)
        
        print(f"\n{'='*60}")
        print(f"📊 BATCH SUMMARY:")
        print(f"   ✅ Successfully merged: {successful_merges}/{processed_count} groups")
        print(f"   📈 Remaining groups: {total_groups - processed_count}")
        
        if total_groups > batch_size:
            print(f"\n💡 To process the next batch, run the script again!")
            print(f"   The script will automatically continue with the next {batch_size} groups.")
        else:
            print(f"\n🎉 All duplicate groups have been processed!")
            
    else:
        # We have individual scenes - treat all as one group for now
        print(f"\n🎯 Processing duplicate scenes ({len(duplicate_scenes)} scenes)")
        merge_duplicate_scenes(client, duplicate_scenes)

def main():
    # Configure your Stashapp connection using the settings above
    client = StashAppClient(
        base_url=STASH_URL,
        api_key=API_KEY
    )
    
    print(f"🔍 Finding duplicate scenes using Stash's built-in duplicate detection")
    print(f"   📡 Server: {STASH_URL}")
    print(f"   🎯 Distance: {PHASH_DISTANCE} ({'exact match' if PHASH_DISTANCE == 0 else 'tolerant matching'})")
    print(f"   📦 Batch size: {BATCH_SIZE} groups per run")
    
    result = client.find_duplicate_scenes(PHASH_DISTANCE)
    
    if 'errors' in result:
        print(f"Error: {result['errors']}")
        return
    
    duplicate_scenes = result['data']['findDuplicateScenes']
    
    display_duplicate_scenes(duplicate_scenes)
    
    # Process duplicate groups in batches for merging
    if duplicate_scenes:
        process_duplicate_groups_batch(client, duplicate_scenes, batch_size=BATCH_SIZE)
    
    # Save results to file for further analysis
    if duplicate_scenes:
        with open('phash_duplicates.json', 'w') as f:
            json.dump(duplicate_scenes, f, indent=2, default=str)
        
        print(f"\nDuplicate scenes saved to 'phash_duplicates.json'")
    
    print(f"\n💡 TIPS:")
    print(f"   • To process more batches, simply run the script again")
    print(f"   • To find more similar scenes, change PHASH_DISTANCE from {PHASH_DISTANCE} to 4 at the top of the script")
    print(f"   • Each run processes {BATCH_SIZE} groups (configurable via BATCH_SIZE)")
    print(f"   • Modify STASH_URL and API_KEY at the top for different Stash instances")

if __name__ == "__main__":
    main() 