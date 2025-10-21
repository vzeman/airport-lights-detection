# UI VERSION OF PROCESSING PAPI lights on airport

We need application with userinterface, which could run as standalone application on any computer or as docker on macbook or windows based computer


## Goal of application
Compute from video recorded by drone angles when the lights are visible and when they change colors from red to white or white to red.
Video contains exact positions of the drone and position of gimbal
Also as input will be given information about the lights and their position.

## DATA 
- airports (AIRPORT_ICAO_CODE, NAME) - add slovak airports from Bratislava, Trencin Piestany, Zilina, Kosice, Poprad, Prievidza
- runways (AIRPORT_ICAO_CODE, RNWY_CODE, Name)
- reference_points (AIRPORT_ICAO_CODE, RNWY_CODE, ID, latitude, longitude, elevation_WGS_84, Type) - Type can be value [PAPI_A/PAPI_B/PAPI_C/PAPI_D/TOUCH_POINT]

## Workflow of application
1. 1.Step - Form will show list of airports - user needs to choose the airport 
2. After airport selected, user will see list of runways - user needs to choose runway
3. user will upload video he recorded in drone for given runway
4. we will extract first image from video and identify all lights in the image, in the video is to the frame assigned also exact position of the drone, gimbal position, elevation. use these information to identify in the first image lights and assign PAPI_A, PAPI_B, PAPI_C and PAPI_D from reference points on the image 
5. User will see the picture with rectangles representing PAPI lights, user should be able to move rectangles if automatic recognition was incorrect - based on this selection will know application which light is PAPI.
6. after user confirms reference points in the first video, we can start processing video:
- for each frame in video extract image, lat, long, elevation, gimbal position 
- in each frame identify again position of PAPI lights selected in initial frame and track the movement (hint: all PAPI lights will move in the same direction on video as drone is flying, make sure we will properly track the positions of PAPI ligths in video)
- we will create for each PAPI light small video of the rectangle around the PAPI light, which will show how the light was changing as the drone was flying, given light will be centered during whole time of video of PAPI light and will show just this single light
- for each PAPI light we will evaluate in each frame RGB values of the light - for each frame we should identify intensity, overall color, RGB values, categorize it with following categories [not_visible, red, white, transition] ... transition value is when the color is chaning as the drone is flying from red to white or from white to red
- for each frame and for each PAPI light we will evaluate angle between ground and drone and distance of drone (distance on the ground but also direct distance to drone) of the light (we know position of each light and elevation and we know also position and elevation of the drone in each frame - use simple math to compute angle and both types of distances)
- Generate HTML report where will be on X axis time, on Y axis will be values RGB of the light and on another Y axis will be angle of the drone in given frame


## reference example
use same libraries and algorithms we evaluated already in the script analyze_lights.py