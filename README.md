# BandcampSync

BandcampSync is a Python module and command line script (also packed in
a Docker container) which synchronises media purchased on a Bandcamp
(http://bandcamp.com/) account with a local directory.

You may use this to download media you have purchased from Bandcamp to a
local media server, such as Plex or Jellyfin.

Most media items purchased on Bandcamp have high quality download options
available and BandcampSync defaults to `flac`.

When called, `bandcampsync` will:

1. Authenticate to bandcamp.com as you using your exported session cookies
2. Scan your local media directory for existing downloaded items
3. Index a list of all of your purchased items in your Bandcamp collection
4. Download the archive of missing items not downloaded already from your collection
5. Unzip the archive and move the contents to the local media directory

The media directory will have the following format:

```
/media/
/media/Artist Name
/media/Artist Name/Album Name
/media/Artist Name/Album Name/bandcamp_item_id.txt
/media/Artist Name/Album Name/cover.jpg
/media/Artist Name/Album Name/Track Name.flac
```

The directory format of `artist_name`/`item_title` is not editable.

`bandcamp_item_id.txt` is a special file created in each item directory and
it contains the Bandcamp item ID as an integer. This file is used by BandcampSync
to track which media items have already been downloaded. You can rename the
artist or album directories, but do not delete the `bandcamp_item_id.txt` file
or the media item will be redownloaded the next time `bandcampsync` is run.

The `bandcamp_item_id.txt` file method of tracking what items are synchronised
also means you can also use media managers such as Lidarr to rename artist,
album and track names automatically without issues.


## Installation

`bandcampsync` is pure Python and only has a dependancy on the `requests` and
`beautifulsoup4` libraries. You can install `bandcampsync` via pip:

```bash
$ pip install bandcampsync
```

Any modern version of Python3 will be compatible.

Alternatively, there's a batteries included Docker image available if you prefer.


## Docker

The Docker image contains the `bandcampsync` Python module as well as a helper
script that runs the `bandcampsync` on a timer. Configuration variables are also
moved to environment variables

You can pull and run the image with the following commands:

```bash
# Pull image
$ docker pull ghcr.io/meeb/bandcampsync:latest
# Start the container using your user ID and group ID
$ docker run \
  -d \
  --name bandcampsync \
  -e TZ=Europe/London \
  -e PUID=1000 \
  -e PGID=1000 \
  -e RUN_DAILY_AT=3 \
  -v /some/directory/bandcampsync-config:/config \
  -v /some/directory/bandcampsync-media:/downloads \
  ghcr.io/meeb/bandcampsync:latest

```

Or an example Docker Compose entry:

```bash
version: '3.7'
services:
  bandcampsync:
    image: ghcr.io/meeb/bandcampsync:latest
    container_name: bandcampsync
    restart: unless-stopped
    volumes:
      - /some/directory/bandcampsync-config:/config
      - /some/directory/bandcampsync-media:/downloads
    environment:
      - TZ=Europe/London
      - PUID=1000
      - PGID=1000
      - RUN_DAILY_AT=3
```

In the above example you would save your cookies data into a file called
`cookies.txt` and save it at `/some/directory/bandcampsync-config/cookies.txt`.
BandcampSync will look for this location when it starts up.

The `RUN_DAILY_AT` environment variable is the hour the `bandcampsync` script
will run at. In this example, 3am local time. After running the container will
sleep until the following 3am. It will run daily. There is also a randomised
delay added to the hour to not dogpile bandcamp.com with requests on the hour 
so the script won't run exactly on the hour.

`RUN_DAILY_AT` should be a number between 0 and 23 (specifying an hour).

`PUID` and `PGID` are the user and group IDs to attempt run the download as.
This sets the UID and GID of the files that are downloaded.

`TEMP_DIR` variable can be set to a directory in the container. If set the
directory is used as the temporary download location.


## Configuration

BandcampSync requires minimial configuration. First, it requires your session
cookies from an authenticated Bandcamp account. The easiest way to get this is
to go to https://bandcamp.com/ in your browser and log in with your account.

Next, open the developer tools in your browser (F12 button on most browsers, or
select "developer tools" from the options menu).

Reload the index page and find the index page request in your network requests
tab of your browser. Go to the "Request Headers" section then select and copy
the string after the `Cookie` header. The string should look something like this:

```
client_id=00B1F3C8EB48E181A185CCD041E40C0E8F; session=1%0893C88%570EE405455%%8DEC37B5BC393983DB983DD%%BDFD46C3B8A0%%580DA466D5CD; identity=1%HhehuehUFEUiuebn%%2ADB72300DAE573%BEEF389A1B526EA35AC38019FA0A6F%11B4BD5FBC18B83F720; js_logged_in=1; logout=%7B%22username%22%3A%22someuser%22%7D; download_encoding=401; BACKENDID3=some-sever-name
```

Save this string to a file called `cookies.txt`.

![Getting your session cookues](https://github.com/meeb/bandcampsync/blob/main/docs/cookies.jpg?raw=true)

You need to save your session ID from cookies manually because Bandcamp has
a captcha on the login form so BandcampSync can't log in with your username
and password for you.

IMPORTANT NOTE: Keep the `cookies.txt` file safe! Anyone with access to this file
can log into your Bandcamp account, impersonate you, potentially make purchases
and generally have total access to your Bandcamp account!


## CLI usage

Once you have the Python `bandcampsync` module installed you can call it with the
`bandcampsync` command:

```bash
$ bandcampsync --cookies cookies.txt --directory /path/to/music
```

or in shorthand:

```bash
$ bandcampsync -c cookies.txt -d /path/to/music
```

You can also use `-t` or `--temp-dir` to set the temporary download directory used. See
`-h` or `--help` for the full list of command line options.

## Formats

By default, BandcampSync will download your music in the `flac` format. You can specify
another format with the `--format` argument. Common Bandcamp download formats are:

| Name            | Description                                                     |
| --------------- | --------------------------------------------------------------- |
| `mp3-v0`        | Variable bitrate MP3. Small file sizes. OK quality.             |
| `mp3-320`       | High quality MP3. Medium file sizes. Good quality.              |
| `flac`          | Losses audio. Large file sizes. Original Quality.               |
| `aac-hi`        | Apple variable bitrate format. Small file sizes. OK quality.    |
| `aiff-lossless` | Uncompressed audio format. Biggest file size. Original quality. |
| `vorbis`        | Open source lossy format. Small file sizes. OK quality.         |
| `alac`          | Apple lossless format. Large file sizes. Original quality.      |
| `wav`           | Uncompressed audio format. Biggest file size. Original quality. |

You can also use `-i` or `--ignore` to bypass artists that have data issues that
your OS can not handle.

```bash
$ bandcampsync --cookies cookies.txt --directory /path/to/music --ignore "badband"
```

# Contributing

All properly formatted and sensible pull requests, issues and comments are welcome.
