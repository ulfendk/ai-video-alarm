I run Home Assistant with FrigateNVR. It is ok, but does not work as I would have hoped it does. There
are too many false alarms, due to the way it detects motion. It detects motion in the video, then analyses
for object in that field. So, let's say a bird flies by a bicycle - then Frigate triggers an alarm for a
bicycle, when in fact the culprit was a bird.

Design a solution for me, which will run in a Docker container, and allow for integration with HA over
MQTT. I have a Google Coral device for image analysis, and I would consider using an online AI service
to analyze photos, when there's a high chance of a real hit (e.g. "We are not home and this is the scene
of the front porch - should I be alerted?").

I also want to leverage snapshotting features of the cameras, so I can quickly get a picture of who's at
the front door, ringing it.

Special considerations include harder analysis, when it's dark (my cameras are Dahua with low light capabilities,
rather than IR).

I originally wanted to use the system to compensate for flawed PIR detection, for outdoor lighting, to
reduce false positives from e.g. the neighbour's cat walking through our yard.

I also want an archive of relevant photos and videos to go back through (quota'd such that oldest are removed,
nearing the threshold).

The integration with HA must be great - easy triggers and easy use of the photos / videos in push notifications
and/or IMs, email, etc.

I don't expect to run this as a HA addon, but I do want an add-on (app) for HA to proxy through to this solution, since 
it'll be running of different hardware.

Finally, this should be configurable as a nice alarm system, well integrated with HA. I currently, mostly rely on the
"presence simulation" plugin, which allows me to play back last week's lighting, when not at home. That's great, but
not enough.

I have electronic locks on my doors.

Do not assume - ask me clarifying questions about the setup and environment where this is meant to run.
