import requests
import json

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
    
    def find_scenes_with_multiple_files(self):
        query = """
        query FindScenesWithMultipleFiles {
          findScenes(scene_filter: {
            file_count: {
              value: 1
              modifier: GREATER_THAN
            }
          }) {
            count
            scenes {
              id
              title
              files {
                id
                path
                video_codec
                basename
              }
            }
          }
        }
        """
        return self.execute_query(query)
    
    def set_primary_file(self, scene_id, file_id):
        mutation = """
        mutation SetMKVAsPrimary($scene_id: ID!, $file_id: ID!) {
          sceneUpdate(input: {
            id: $scene_id
            primary_file_id: $file_id
          }) {
            id
            title
          }
        }
        """
        variables = {
            'scene_id': scene_id,
            'file_id': file_id
        }
        return self.execute_query(mutation, variables)
    
    def delete_file(self, file_id):
        mutation = """
        mutation DeleteFile($file_id: ID!) {
          deleteFiles(ids: [$file_id])
        }
        """
        variables = {
            'file_id': file_id
        }
        return self.execute_query(mutation, variables)

def main():
    # Configure your Stashapp connection
    client = StashAppClient(
        base_url="http://ifyouseek8:9999",
        api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiJwc3ljaG9ob2xpYyIsImlhdCI6MTY5OTczNzkyNCwic3ViIjoiQVBJS2V5In0.XDs7C0TyfcUp13Kg_lSVl-A7HYA5h6lHZ92_lX9b1Zo"
    )
    
    # Find scenes with multiple files
    result = client.find_scenes_with_multiple_files()
    
    if 'errors' in result:
        print(f"Error: {result['errors']}")
        return
    
    scenes = result['data']['findScenes']['scenes']
    total_scenes = len(scenes)
    processed_count = 0
    batch_size = 100
    
    print(f"Found {total_scenes} scenes with multiple files")
    print(f"Processing in batches of {batch_size}...")
    
    # Process scenes in batches of 10
    for i in range(0, total_scenes, batch_size):
        batch = scenes[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        print(f"\nProcessing batch {batch_num} ({len(batch)} scenes)...")
        
        for scene in batch:
            mp4_files = [f for f in scene['files'] if f['path'].lower().endswith('.mp4')]
            mkv_files = [f for f in scene['files'] if f['path'].lower().endswith('.mkv')]
            
            if mp4_files and mkv_files:
                mkv_file = mkv_files[0]
                mp4_file = mp4_files[0]
                
                # Set MKV as primary
                result = client.set_primary_file(scene['id'], mkv_file['id'])
                
                if 'errors' not in result:
                    print(f"✓ Set MKV as primary for: {scene['title']}")
                    
                    # Delete the MP4 file
                    delete_result = client.delete_file(mp4_file['id'])
                    
                    if 'errors' not in delete_result:
                        processed_count += 1
                        print(f"✓ Deleted MP4 file: {mp4_file['basename']}")
                    else:
                        print(f"✗ Error deleting MP4 file for: {scene['title']} - {delete_result['errors']}")
                else:
                    print(f"✗ Error setting primary file for: {scene['title']} - {result['errors']}")
        
        # Add a pause between batches (optional)
        if i + batch_size < total_scenes:
            input(f"\nBatch {batch_num} completed. Press Enter to continue to next batch...")
    
    print(f"\nCompleted! Successfully processed {processed_count} scenes.")
    print(f"Set MKV as primary and deleted MP4 files for {processed_count} scenes.")

if __name__ == "__main__":
    main()