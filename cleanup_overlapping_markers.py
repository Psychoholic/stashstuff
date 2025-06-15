#!/usr/bin/env python3
"""
Stash Scene Marker Cleanup Script

This script finds scenes with overlapping markers (markers that start at the same time)
and removes all but the marker with the lowest ID for each overlapping group.

Author: Assistant
"""

import requests
import json
import time
import os
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv

# ====== CONFIGURATION ======
CONFIG = {
    'per_page': 100,            # Number of scenes to fetch per page
    'test_mode': False,        # Set to True to process only one scene for testing
    'max_scenes': 10,          # Set to a number to limit total scenes processed (None = all)
    'dry_run': True,           # Set to False to actually delete markers
    'rate_limit_delay': 0.1,   # Delay between API calls (seconds)
    'within_seconds': 2,       # Markers within this many seconds are considered overlapping
}

class StashMarkerCleaner:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            'Content-Type': 'application/json',
            'ApiKey': api_key
        }
        self.graphql_url = f"{base_url}/graphql"
        self.dry_run = CONFIG['dry_run']
        self.test_mode = CONFIG['test_mode']
        
    def execute_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute a GraphQL query"""
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
            
        response = requests.post(self.graphql_url, json=payload, headers=self.headers)
        result = response.json()
        
        if 'errors' in result:
            print(f"GraphQL Error: {result['errors']}")
            return {}
            
        return result
    
    def get_scenes_with_markers(self) -> List[Dict]:
        """Get all scenes that have markers (basic info only), starting with highest IDs"""
        query = """
        query FindScenesWithMarkers($page: Int!, $per_page: Int!) {
          findScenes(
            scene_filter: { 
              has_markers: "true" 
            }
            filter: { 
              page: $page, 
              per_page: $per_page,
              sort: "id",
              direction: DESC
            }
          ) {
            count
            scenes {
              id
              title
            }
          }
        }
        """
        
        all_scenes = []
        page = 1
        per_page = CONFIG['per_page']
        
        while True:
            print(f"Fetching scenes with markers, page {page}...")
            result = self.execute_graphql(query, {"page": page, "per_page": per_page})
            
            if not result or 'data' not in result:
                break
                
            scenes = result['data']['findScenes']['scenes']
            if not scenes:
                break
                
            all_scenes.extend(scenes)
            print(f"  Found {len(scenes)} scenes with markers on this page")
            
            # In test mode, just process the first scene found
            if self.test_mode and scenes:
                print(f"🧪 TEST MODE: Processing only the first scene found (ID: {scenes[0]['id']})")
                all_scenes = [scenes[0]]
                break
            
            # Check if we've got all pages
            if len(scenes) < per_page:
                break
                
            page += 1
            time.sleep(CONFIG['rate_limit_delay'])  # Be nice to the API
        
        print(f"Total scenes with markers: {len(all_scenes)}")
        return all_scenes
    
    def get_scene_markers(self, scene_id: str) -> List[Dict]:
        """Get all markers for a specific scene"""
        query = """
        query GetSceneMarkers($scene_id: Int!) {
          findSceneMarkers(
            scene_marker_filter: {
              scene_filter: {
                id: {
                  value: $scene_id,
                  modifier: EQUALS
                }
              }
            }
            filter: {
              per_page: 1000  # Should be enough for any single scene
            }
          ) {
            count
            scene_markers {
              id
              seconds
              end_seconds
              title
              primary_tag {
                id
                name
              }
            }
          }
        }
        """
        
        # Convert scene_id to integer as expected by the GraphQL schema
        scene_id_int = int(scene_id)
        result = self.execute_graphql(query, {"scene_id": scene_id_int})
        
        if not result or 'data' not in result:
            return []
            
        return result['data']['findSceneMarkers']['scene_markers']
    
    def find_overlapping_markers(self, scene: Dict) -> List[List[Dict]]:
        """Find groups of markers that start within the configured time tolerance"""
        markers = scene['markers']
        within_seconds = CONFIG['within_seconds']
        
        # Sort markers by start time for easier processing
        sorted_markers = sorted(markers, key=lambda x: x['seconds'])
        
        overlapping_groups = []
        used_markers = set()
        
        for i, marker in enumerate(sorted_markers):
            if marker['id'] in used_markers:
                continue
                
            # Find all markers within the time tolerance
            group = [marker]
            used_markers.add(marker['id'])
            
            for j, other_marker in enumerate(sorted_markers[i+1:], i+1):
                if other_marker['id'] in used_markers:
                    continue
                    
                time_diff = abs(other_marker['seconds'] - marker['seconds'])
                if time_diff <= within_seconds:
                    group.append(other_marker)
                    used_markers.add(other_marker['id'])
                else:
                    # Since markers are sorted by time, no more overlaps possible
                    break
            
            # Only consider it an overlapping group if more than one marker
            if len(group) > 1:
                # Sort by ID to ensure we keep the lowest ID
                group.sort(key=lambda x: int(x['id']))
                overlapping_groups.append(group)
        
        return overlapping_groups
    
    def delete_marker(self, marker_id: str) -> bool:
        """Delete a scene marker by ID"""
        if self.dry_run:
            print(f"    [DRY RUN] Would delete marker {marker_id}")
            return True
            
        mutation = """
        mutation SceneMarkerDestroy($id: ID!) {
          sceneMarkerDestroy(id: $id)
        }
        """
        
        result = self.execute_graphql(mutation, {"id": marker_id})
        
        if result and 'data' in result:
            print(f"    ✓ Deleted marker {marker_id}")
            return True
        else:
            print(f"    ✗ Failed to delete marker {marker_id}")
            return False
    
    def process_scene_markers(self, scene: Dict) -> Tuple[int, int]:
        """Process a single scene - get its markers and clean up overlapping ones"""
        scene_id = scene['id']
        scene_title = scene['title']
        
        # Get all markers for this scene
        markers = self.get_scene_markers(scene_id)
        
        if not markers:
            return 0, 0
        
        print(f"\nScene: {scene_title} (ID: {scene_id})")
        print(f"  Found {len(markers)} total markers")
        
        # Create scene object with markers for the existing logic
        scene_with_markers = {
            'id': scene_id,
            'title': scene_title,
            'markers': markers
        }
        
        overlapping_groups = self.find_overlapping_markers(scene_with_markers)
        
        if not overlapping_groups:
            print(f"  No overlapping markers found")
            return 0, 0
        
        print(f"  Found {len(overlapping_groups)} groups of overlapping markers")
        
        total_markers = 0
        deleted_markers = 0
        
        for group in overlapping_groups:
            start_times = [marker['seconds'] for marker in group]
            time_range = f"{min(start_times):.1f}s-{max(start_times):.1f}s" if min(start_times) != max(start_times) else f"{min(start_times):.1f}s"
            print(f"  Group at {time_range}: {len(group)} markers")
            
            # Keep the first marker (lowest ID), delete the rest
            keeper = group[0]
            to_delete = group[1:]
            
            print(f"    Keeping: ID {keeper['id']} - {keeper['title']} ({keeper['primary_tag']['name'] if keeper['primary_tag'] else 'No tag'})")
            
            for marker in to_delete:
                tag_name = marker['primary_tag']['name'] if marker['primary_tag'] else 'No tag'
                print(f"    Deleting: ID {marker['id']} - {marker['title']} ({tag_name})")
                
                if self.delete_marker(marker['id']):
                    deleted_markers += 1
                    
                time.sleep(CONFIG['rate_limit_delay'])  # Rate limiting
            
            total_markers += len(group)
        
        return total_markers, deleted_markers
    
    def run_cleanup(self):
        """Main cleanup process"""
        print("=" * 60)
        print("STASH SCENE MARKER CLEANUP")
        print("=" * 60)
        
        if self.dry_run:
            print("🚨 DRY RUN MODE - No markers will actually be deleted")
            print("   Set CONFIG['dry_run']=False to perform actual deletions")
            print()
        
        if self.test_mode:
            print("🧪 TEST MODE - Processing only one scene")
            print("   Set CONFIG['test_mode']=False to process all scenes")
            print()
        
        # Get all scenes that have markers
        scenes = self.get_scenes_with_markers()
        
        if not scenes:
            print("No scenes with markers found.")
            return
        
        total_scenes_processed = 0
        total_overlapping_markers = 0
        total_deleted_markers = 0
        scenes_with_overlaps = 0
        
        # Apply max_scenes limit if specified
        if CONFIG['max_scenes'] is not None:
            scenes = scenes[:CONFIG['max_scenes']]
            print(f"🔢 Limiting to first {CONFIG['max_scenes']} scenes")
            print()
        
        for i, scene in enumerate(scenes):
            print(f"\n[{i+1}/{len(scenes)}] Processing scene: {scene['title']} (ID: {scene['id']})")
            
            overlapping_markers, deleted_markers = self.process_scene_markers(scene)
            
            if overlapping_markers > 0:
                scenes_with_overlaps += 1
                total_overlapping_markers += overlapping_markers
                total_deleted_markers += deleted_markers
            
            total_scenes_processed += 1
            
            # Progress update every 25 scenes (less frequent since we have per-scene updates now)
            if total_scenes_processed % 25 == 0:
                print(f"\n📊 Progress Update: {total_scenes_processed}/{len(scenes)} scenes processed")
                print(f"   Scenes with overlaps so far: {scenes_with_overlaps}")
                print(f"   Overlapping markers found: {total_overlapping_markers}")
                if self.dry_run:
                    print(f"   Markers that would be deleted: {total_deleted_markers}")
                else:
                    print(f"   Markers deleted: {total_deleted_markers}")
        
        # Final summary
        print("\n" + "=" * 60)
        print("CLEANUP SUMMARY")
        print("=" * 60)
        print(f"Total scenes processed: {total_scenes_processed}")
        print(f"Scenes with overlapping markers: {scenes_with_overlaps}")
        print(f"Total overlapping markers found: {total_overlapping_markers}")
        
        if self.dry_run:
            print(f"Markers that would be deleted: {total_deleted_markers}")
        else:
            print(f"Markers successfully deleted: {total_deleted_markers}")
        
        if total_deleted_markers > 0:
            print(f"Space saved: {total_overlapping_markers - (scenes_with_overlaps)} markers removed")

def main():
    # Load credentials from stash.env file
    load_dotenv('stash.env')
    
    BASE_URL = os.getenv('STASH_URL')
    API_KEY = os.getenv('STASH_API_KEY')
    
    if not BASE_URL or not API_KEY:
        print("❌ Error: Could not find STASH_URL and STASH_API_KEY in stash.env file")
        print("Please ensure your stash.env file contains:")
        print("STASH_URL=http://your-stash-url:port")
        print("STASH_API_KEY=your-api-key")
        return
    
    print(f"🔗 Connecting to Stash at: {BASE_URL}")
    print(f"📊 Configuration: per_page={CONFIG['per_page']}, test_mode={CONFIG['test_mode']}, dry_run={CONFIG['dry_run']}, within_seconds={CONFIG['within_seconds']}")
    print()
    
    cleaner = StashMarkerCleaner(BASE_URL, API_KEY)
    
    print("Starting cleanup process...")
    print("This will identify overlapping markers and remove duplicates.")
    print("Only markers with the lowest ID will be kept for each overlap group.")
    print()
    
    cleaner.run_cleanup()

if __name__ == "__main__":
    main() 