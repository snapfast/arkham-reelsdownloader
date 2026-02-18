# for production 

first run build_prod.sh file
then run cookies_upload.sh file


# for local

only run run_local.sh file

------------------------------------------

Two endpoints:

POST /formats — check what qualities are available for a video


curl -X POST "http://localhost:8080/formats" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.youtube.com/watch?v=2fhRNk3HywI"}'

{
  "input_url": "https://www.youtube.com/watch?v=2fhRNk3HywI",
  "available_qualities": [360, 480, 720]
}
POST /resolve — get the direct media URL for a specific quality


curl -X POST "http://localhost:8080/resolve" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.youtube.com/watch?v=2fhRNk3HywI", "quality": 720}'

{
  "input_url": "https://www.youtube.com/watch?v=2fhRNk3HywI",
  "quality": 720,
  "media_url": "https://rr3---sn-xxx.googlevideo.com/videoplayback?..."
}
Valid quality values: 360, 480, 720, 1080, 2160. Passing anything else returns a 400.

Typical usage: call /formats first to know what to offer the user, then call /resolve with the chosen quality


