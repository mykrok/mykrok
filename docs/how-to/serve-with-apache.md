# Serve with Apache

Host your MyKrok browser on an Apache web server.

## Basic Setup

Copy the generated browser and data to your web root:

```bash
# Generate the browser
mykrok create-browser

# Copy to web directory
cp -r data/ /var/www/html/mykrok/
cp data/mykrok.html /var/www/html/mykrok/
```

The browser should now be accessible at `http://your-server/mykrok/mykrok.html`.

## Apache with DataLad/git-annex

When using DataLad or git-annex in **locked mode** (the default), files are stored as symlinks pointing to the annex. Apache needs special configuration to follow these symlinks.

### The Problem

By default, Apache won't follow symlinks outside the document root for security reasons. With git-annex locked mode, your files look like:

```
data/athl=user/ses=20251218T063000/photos/photo.jpg
  -> ../.git/annex/objects/XX/YY/SHA256E-s12345--abc123.jpg/SHA256E-s12345--abc123.jpg
```

Apache will return 403 Forbidden or 404 Not Found for these files.

### Solution: Enable FollowSymLinks

Configure Apache to follow symlinks in your MyKrok directory.

#### Option 1: Directory Configuration

Add to your Apache site configuration (e.g., `/etc/apache2/sites-available/000-default.conf`):

```apache
<Directory /var/www/html/mykrok>
    Options +FollowSymLinks
    AllowOverride None
    Require all granted
</Directory>
```

Then reload Apache:

```bash
sudo systemctl reload apache2
```

#### Option 2: .htaccess File

If `AllowOverride` is enabled, create a `.htaccess` file in your MyKrok directory:

```apache
Options +FollowSymLinks
```

!!! warning "Security Consideration"
    `FollowSymLinks` allows Apache to serve files outside the document root via symlinks. Ensure your annex directory permissions are properly set and the symlinks only point to intended files.

### Verify git-annex Content is Available

Before serving, ensure the annexed content is present:

```bash
cd /var/www/html/mykrok/data

# Check if content is available
git annex whereis

# Get all content if needed
datalad get .
```

### Alternative: Unlock Files

Instead of configuring Apache for symlinks, you can unlock the files to convert symlinks to regular files:

```bash
cd /var/www/html/mykrok/data
git annex unlock .
```

!!! note
    Unlocking creates copies of the files, using more disk space. This may be preferable for simpler deployment but loses the space-saving benefits of git-annex.

## Recommended Apache Configuration

A complete example for serving MyKrok with DataLad:

```apache
<VirtualHost *:80>
    ServerName mykrok.example.com
    DocumentRoot /var/www/html/mykrok

    <Directory /var/www/html/mykrok>
        Options +FollowSymLinks +Indexes
        AllowOverride None
        Require all granted

        # Enable CORS for Parquet file loading
        Header set Access-Control-Allow-Origin "*"
    </Directory>

    # Cache static assets
    <LocationMatch "\.(jpg|jpeg|png|parquet|json)$">
        Header set Cache-Control "max-age=86400, public"
    </LocationMatch>

    ErrorLog ${APACHE_LOG_DIR}/mykrok-error.log
    CustomLog ${APACHE_LOG_DIR}/mykrok-access.log combined
</VirtualHost>
```

Enable required modules:

```bash
sudo a2enmod headers
sudo systemctl reload apache2
```

## Other Web Servers

### nginx

nginx follows symlinks by default. No special configuration needed:

```nginx
server {
    listen 80;
    server_name mykrok.example.com;
    root /var/www/html/mykrok;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

### Python's Built-in Server

For local testing, Python's server follows symlinks:

```bash
cd /path/to/mykrok/data
python -m http.server 8080
```

Or use the built-in option:

```bash
mykrok create-browser --serve
```
