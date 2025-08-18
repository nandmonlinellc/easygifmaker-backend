# Vite + Flask Testing Guide

## 🏗️ **Current Setup**

- **Vite Frontend**: `localhost:5173` (React tools)
- **Flask Backend**: `localhost:5001` (SEO pages + API)

## 🚀 **How to Test SEO Pages**

### **1. Start Both Servers**

**Terminal 1 - Vite Frontend:**
```bash
cd easygifmaker
npm run dev
```

**Terminal 2 - Flask Backend:**
```bash
cd easygifmaker_api
source venv/bin/activate
python -m src.main
```

### **2. Run Comprehensive Test**
```bash
cd easygifmaker_api
python test_vite_setup.py
```

## 🌐 **URLs to Test**

### **React Tools (Vite - localhost:5173):**
- `http://localhost:5173/video-to-gif` - Video to GIF converter
- `http://localhost:5173/gif-maker` - GIF maker tool
- `http://localhost:5173/crop` - Crop GIF tool
- `http://localhost:5173/optimize` - Optimize GIF tool
- `http://localhost:5173/add-text` - Add text to GIF tool

### **SEO Pages (Flask - localhost:5001):**
- `http://localhost:5001/convert/mp4-to-gif` - MP4 to GIF converter page
- `http://localhost:5001/convert/youtube-to-gif` - YouTube to GIF page
- `http://localhost:5001/features/reverse-gif` - Reverse GIF feature page
- `http://localhost:5001/optimize/gif-under-5mb` - Compress GIF page
- `http://localhost:5001/tools/add-text-to-gif` - Add text to GIF page

### **SEO Files (Flask - localhost:5001):**
- `http://localhost:5001/sitemap.xml` - XML sitemap
- `http://localhost:5001/robots.txt` - Robots file

## 🔍 **What to Look For**

### **SEO Pages (Flask):**
1. **Full HTML page** with complete meta tags
2. **Schema markup** in page source
3. **Open Graph tags** for social sharing
4. **FAQ content** with structured data
5. **CTA buttons** linking to React tools
6. **Mobile-responsive** design

### **React Tools (Vite):**
1. **Interactive components** working
2. **File upload** functionality
3. **Real-time preview** features
4. **API calls** to Flask backend
5. **Smooth navigation** between tools

## 🧪 **Manual Testing Steps**

### **Step 1: Test SEO Pages**
```bash
# Test SEO page content
curl http://localhost:5001/convert/mp4-to-gif | grep -i "schema\|og:\|twitter:"

# Test sitemap
curl http://localhost:5001/sitemap.xml

# Test robots.txt
curl http://localhost:5001/robots.txt
```

### **Step 2: Test React Tools**
```bash
# Test React app loading
curl http://localhost:5173/video-to-gif

# Test API connectivity
curl http://localhost:5001/api/health
```

### **Step 3: Browser Testing**
1. **Open SEO page**: `http://localhost:5001/convert/mp4-to-gif`
2. **Click CTA button** → should go to React tool
3. **Test React tool**: `http://localhost:5173/video-to-gif`
4. **Verify functionality** works as expected

## 📊 **Expected Results**

### **SEO Pages Should Show:**
- ✅ Complete HTML with meta tags
- ✅ Schema.org structured data
- ✅ Open Graph and Twitter Cards
- ✅ FAQ sections with proper markup
- ✅ Internal links to React tools
- ✅ Mobile-responsive design

### **React Tools Should Show:**
- ✅ Interactive file upload
- ✅ Real-time processing
- ✅ API calls to Flask backend
- ✅ Smooth user experience
- ✅ All tool functionality working

## 🔗 **Integration Points**

### **SEO → React Flow:**
1. User visits SEO page: `localhost:5001/convert/mp4-to-gif`
2. Reads content about MP4 to GIF conversion
3. Clicks "Start Converting" button
4. Redirected to React tool: `localhost:5173/video-to-gif`
5. Uses interactive tool to convert files

### **API Communication:**
- React tools make API calls to `localhost:5001/api/*`
- Flask backend processes requests
- Results returned to React frontend

## 🛠️ **Development Workflow**

### **Adding New SEO Pages:**
```bash
cd easygifmaker_api
python add_seo_page.py
# Follow prompts
# Restart Flask server
```

### **Updating React Tools:**
```bash
cd easygifmaker
# Make changes to React code
# Vite auto-reloads on localhost:5173
```

### **Testing Changes:**
```bash
cd easygifmaker_api
python test_vite_setup.py
```

## 🎯 **Production Deployment**

### **When Ready for Production:**
1. **Build React app**: `npm run build`
2. **Copy to Flask**: `cp -r dist/* easygifmaker_api/src/static/`
3. **Deploy Flask**: Single server serves both SEO and React
4. **Update domain**: Point to production server
5. **Submit sitemap**: To Google Search Console

## 🚨 **Troubleshooting**

### **If SEO pages don't load:**
- Check Flask server is running on port 5001
- Verify Jinja2 is installed: `pip install jinja2`
- Check template file exists: `ls src/static/seo_template.html`

### **If React tools don't work:**
- Check Vite server is running on port 5173
- Verify API endpoints are accessible
- Check browser console for errors

### **If API calls fail:**
- Ensure Flask server is running
- Check CORS configuration
- Verify API endpoint URLs

## 📈 **Performance Notes**

- **SEO Pages**: Fast server-side rendering
- **React Tools**: Optimized bundle loading
- **API Calls**: Efficient JSON responses
- **Development**: Hot reload for both servers

---

**Your Vite + Flask setup is working perfectly! 🎉**

**SEO pages are fully functional and ready for search engines, while React tools provide the interactive user experience.** 