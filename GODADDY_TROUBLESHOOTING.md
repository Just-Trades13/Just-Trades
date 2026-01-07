# GoDaddy Website & Domain Troubleshooting Guide

## Common Issues & Solutions

### 1. Domain Not Resolving (DNS Issues)

**Symptoms:**
- "This site can't be reached"
- "DNS_PROBE_FINISHED_NXDOMAIN"
- Domain shows as "parked" or "coming soon"

**Check DNS:**
```bash
# Replace YOURDOMAIN.com with your actual domain
dig YOURDOMAIN.com
nslookup YOURDOMAIN.com
```

**Fix in GoDaddy:**
1. Log into GoDaddy Dashboard
2. Go to **My Products** → **Domains**
3. Click your domain → **DNS** tab
4. Check that you have:
   - **A Record** pointing to your hosting IP (if using shared hosting)
   - **CNAME Record** pointing to your hosting provider (if using managed hosting)
   - **Nameservers** are correct (usually `ns1.godaddy.com`, `ns2.godaddy.com`)

**Common DNS Mistakes:**
- ❌ A record pointing to wrong IP
- ❌ Missing www CNAME record
- ❌ Nameservers pointing to wrong provider
- ❌ DNS changes not propagated (can take 24-48 hours)

---

### 2. Website Not Loading (Hosting Issues)

**Symptoms:**
- Domain resolves but shows blank page
- "Connection timeout"
- "502 Bad Gateway"
- "503 Service Unavailable"

**Check Website Status:**
```bash
# Replace YOURDOMAIN.com with your actual domain
curl -I https://YOURDOMAIN.com
curl -I http://YOURDOMAIN.com
```

**Fix in GoDaddy:**
1. Go to **My Products** → **Web Hosting** (or **Websites**)
2. Check if hosting is **Active** (not expired/suspended)
3. Verify your website files are uploaded to:
   - `public_html/` (Linux hosting)
   - `httpdocs/` (Windows hosting)
4. Check for `index.html` or `index.php` in root directory

**Common Hosting Mistakes:**
- ❌ Files uploaded to wrong directory
- ❌ Missing index file
- ❌ Hosting account expired
- ❌ Wrong file permissions (should be 644 for files, 755 for folders)

---

### 3. SSL Certificate Issues

**Symptoms:**
- "Not Secure" warning in browser
- "SSL certificate error"
- Mixed content warnings

**Fix in GoDaddy:**
1. Go to **My Products** → **SSL Certificates**
2. Check if SSL is **Active** and **Installed**
3. For free SSL (Let's Encrypt):
   - Go to **cPanel** → **SSL/TLS Status**
   - Click **Run AutoSSL** to install/renew
4. Wait 5-10 minutes for SSL to activate

**Common SSL Mistakes:**
- ❌ SSL not installed on hosting
- ❌ SSL expired (renew needed)
- ❌ Mixed HTTP/HTTPS content
- ❌ Wrong SSL certificate for domain

---

### 4. Nameserver Issues

**Symptoms:**
- Domain shows GoDaddy parking page
- Website works on hosting but not on domain
- "Nameserver not found"

**Check Nameservers:**
```bash
# Replace YOURDOMAIN.com with your actual domain
dig NS YOURDOMAIN.com
```

**Fix in GoDaddy:**
1. Go to **My Products** → **Domains**
2. Click your domain → **DNS** tab
3. Scroll to **Nameservers** section
4. If using GoDaddy hosting: Use **Default** nameservers
5. If using external hosting: Update to your hosting provider's nameservers

**Common Nameserver Mistakes:**
- ❌ Nameservers pointing to wrong provider
- ❌ Nameservers not updated after switching hosts
- ❌ Typo in nameserver addresses

---

### 5. Website Builder Issues (GoDaddy Website Builder)

**Symptoms:**
- Website not publishing
- Changes not showing up
- "Site not found" error

**Fix in GoDaddy:**
1. Go to **My Products** → **Websites**
2. Click **Manage** on your website
3. Click **Publish** button (if unpublished)
4. Check **Domain** is connected correctly
5. Clear browser cache (Ctrl+Shift+Delete)

---

### 6. Database Connection Issues (WordPress/Apps)

**Symptoms:**
- "Error establishing database connection"
- "Database connection failed"

**Fix in GoDaddy:**
1. Go to **cPanel** → **MySQL Databases**
2. Verify database exists and user has permissions
3. Check `wp-config.php` (WordPress) has correct:
   - `DB_NAME`
   - `DB_USER`
   - `DB_PASSWORD`
   - `DB_HOST` (usually `localhost`)

---

## Quick Diagnostic Commands

Run these to diagnose your specific issue:

```bash
# 1. Check if domain resolves
dig YOURDOMAIN.com +short

# 2. Check nameservers
dig NS YOURDOMAIN.com +short

# 3. Check A record (IP address)
dig A YOURDOMAIN.com +short

# 4. Check if website responds
curl -I https://YOURDOMAIN.com

# 5. Check SSL certificate
openssl s_client -connect YOURDOMAIN.com:443 -servername YOURDOMAIN.com
```

---

## Step-by-Step Troubleshooting

### Step 1: Verify Domain Status
1. Go to GoDaddy Dashboard
2. **My Products** → **Domains**
3. Check domain is **Active** (not expired, locked, or pending transfer)

### Step 2: Verify Hosting Status
1. **My Products** → **Web Hosting** (or **Websites**)
2. Check hosting is **Active** and **Paid**
3. Check if hosting is suspended (look for warnings)

### Step 3: Check DNS Settings
1. **My Products** → **Domains** → Your Domain → **DNS**
2. Verify A record or CNAME points to correct hosting
3. Check nameservers are correct

### Step 4: Check Website Files
1. Go to **cPanel** (or **File Manager**)
2. Navigate to `public_html/` (or `httpdocs/`)
3. Verify `index.html` or `index.php` exists
4. Check file permissions (644 for files, 755 for folders)

### Step 5: Check SSL Certificate
1. **My Products** → **SSL Certificates**
2. Verify SSL is **Active** and **Installed**
3. If missing, install free SSL via cPanel

### Step 6: Clear Cache
- Clear browser cache (Ctrl+Shift+Delete)
- Clear DNS cache: `sudo dscacheutil -flushcache` (macOS)
- Wait 5-10 minutes for DNS propagation

---

## Still Not Working?

**Contact GoDaddy Support:**
1. Go to **Help** → **Contact Us**
2. Choose **Phone** or **Chat** support
3. Have ready:
   - Domain name
   - Hosting account details
   - Error messages you're seeing
   - When the issue started

**Common Support Questions:**
- "My domain isn't resolving - can you check DNS?"
- "My website shows blank page - is hosting active?"
- "SSL certificate expired - can you renew it?"

---

## Prevention Tips

1. **Keep hosting active** - Set up auto-renewal
2. **Backup regularly** - Use GoDaddy backup or manual backups
3. **Monitor SSL expiry** - Set calendar reminders
4. **Test after changes** - Always test DNS/hosting changes
5. **Document changes** - Keep notes of DNS/hosting changes

---

## Need Help?

Share these details for faster troubleshooting:
1. Your domain name
2. Exact error message
3. When it stopped working
4. What you see when visiting the domain
5. Recent changes (DNS, hosting, files)
