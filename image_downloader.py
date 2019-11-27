
# importing google_images_download module
from google_images_download import google_images_download
import sys

# creating object
response = google_images_download.googleimagesdownload()

def downloadimages(query, output_directory, image_directory):
    arguments = {
        "output_directory": output_directory,
        "image_directory": image_directory,
        "keywords": query,
        "format": "jpg",
        "limit": 3,
        "exact_size": "1920,1080"
#        "size": "medium"
#        "silent_mode": True
     }
    response.download(arguments)



if __name__ == '__main__':
    query = sys.argv[-1]
    downloadimages(query)
