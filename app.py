from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
import sqlite3, os

app = Flask(__name__)
app.secret_key = "replace_with_a_random_secret"  # replace with a strong secret for production
DB_FILE = os.path.join(os.path.dirname(__file__), "travel.db")

# ---------------- LOGIN PAGE ----------------
login_template = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Login</title>
<style>
body { margin:0; padding:0; height:100vh; display:flex; align-items:center; justify-content:center; font-family:sans-serif;
       background: linear-gradient(135deg, #6a11cb, #2575fc); }
.login-card { background:#fff; padding:40px 30px; border-radius:12px; box-shadow:0 10px 25px rgba(0,0,0,0.2); text-align:center; width:360px; }
.login-card h2 { margin-bottom:25px; color:#333; font-size:24px; }
.login-card input[type="text"] { width:100%; padding:12px 15px; margin-bottom:20px; border-radius:6px; border:1px solid #ccc; font-size:16px; }
.login-card button { width:100%; padding:12px; border-radius:6px; border:none; background:#2575fc; color:white; font-size:16px; cursor:pointer; transition:background 0.3s ease; }
.login-card button:hover { background:#6a11cb; }
.login-card p { margin-top:15px; font-size:14px; color:#666; }
</style>
</head>
<body>
<div class="login-card">
    <h2>Login</h2>
    <form method="post" style="display:flex; flex-direction:column; gap:15px;">
    <input type="text" name="username" placeholder="Enter username" required style="width:100%; box-sizing:border-box;">
    <button type="submit" style="width:100%;">Login</button>
    </form>
    <p>Welcome! Enter your username to start marking your travels.</p>
</div>
</body>
</html>
"""

# ---------------- MAP PAGE ----------------
map_template = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>World Map Coloring</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/choices.js/public/assets/styles/choices.min.css"/>
<style>
html, body { margin:0; padding:0; height:100%; font-family:sans-serif; }
body { background: linear-gradient(135deg, #6a11cb, #2575fc); display:flex; flex-direction:column; align-items:center; }
#topbar-card { background:#fff; border-radius:12px; padding:15px 20px; margin-top:20px; box-shadow:0 8px 20px rgba(0,0,0,0.2); display:flex; flex-wrap:wrap; align-items:center; gap:16px; width:95%; max-width:1200px; }
#topbar-card label { display:flex; align-items:center; gap:12px; margin:0; font-weight:500; color:#333; }
#topbar-card select, #topbar-card input, #topbar-card button { padding:8px 12px; border-radius:6px; border:1px solid #ccc; height:38px; min-width:200px; font-size:14px; box-sizing:border-box; }
#topbar-card button { cursor:pointer; transition:background 0.3s; }
#topbar-card button:hover { opacity:0.85; }
#topbar-card > div { margin-left:auto; }
#map { flex:1; width:95%; max-width:1200px; margin:20px 0; border-radius:12px; overflow:hidden; min-height:650px; }
.toast { position: fixed; bottom: 20px; right: 20px; background:#333; color:#fff; padding:10px 20px; border-radius:5px; opacity:0.9; z-index:10000; }
.choices__inner { width:200px !important; min-width:200px !important; max-width:200px !important; height:38px !important; line-height:38px !important; padding-top:0 !important; padding-bottom:0 !important; display:flex !important; align-items:center !important; }
.choices__list--single { width:100% !important; }
.choices__list--dropdown { width:200px !important; max-height:200px !important; overflow-y:auto !important; }
.choices__item { white-space: nowrap !important; }
</style>
</head>
<body>

<div id="topbar-card">
  <label>Country:<select id="countrySelect"><option value="">--Select visited--</option></select></label>
  <label>City:<select id="citySelect"><option value="">--Select visited--</option></select></label>
  <label>Pick a color:<input type="color" id="colorInput" value="#ff0000"></label>
  <button onclick="markVisited()" style="background:#2575fc; color:white;">I have been here</button>
  <label>Remove visit:<select id="removeSelect"><option value="">--Select visited--</option></select></label>
  <button onclick="removeVisit()" style="background:#dc3545; color:white;">Remove</button>
  <div><button id="resetBtn" style="background:#6c757d; color:white;">Reset All</button></div>
</div>

<div id="map"></div>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.3.2/papaparse.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/choices.js/public/assets/scripts/choices.min.js"></script>

<script>
var user = "{{ user }}"; // username from session

var map = L.map('map', {zoomControl:false}).setView([20,0],2);
L.control.zoom({position:'topright'}).addTo(map);

var countriesLayer, selectedCountryLayer=null;
var cityMarkers={}, allCities=[], countryChoices, cityChoices, removeChoices;

function showToast(msg){
    var t=document.createElement('div'); t.className='toast'; t.innerText=msg;
    document.body.appendChild(t); setTimeout(()=>t.remove(),2000);
}

function initChoices(selectId){ return new Choices(document.getElementById(selectId), {searchEnabled:true, itemSelectText:'', shouldSort:false}); }

fetch("https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json")
.then(res=>res.json()).then(data=>{
    countriesLayer = L.geoJSON(data,{
        style:{ fillColor:'white', color:'#000', weight:1, fillOpacity:0.3 },
        onEachFeature: function(feature, layer){
            layer.on('mouseover', ()=>layer.setStyle({fillOpacity:0.5}));
            layer.on('mouseout', ()=>layer.setStyle({fillOpacity:0.3}));
        }
    }).addTo(map);

    var countrySet = new Set(data.features.map(f=>f.properties.name));
    countrySet.add("Singapore");
    var countrySelect=document.getElementById('countrySelect');
    [...countrySet].sort().forEach(c=>{ var opt=document.createElement('option'); opt.value=c; opt.text=c; countrySelect.appendChild(opt); });

    countryChoices = initChoices('countrySelect');
    cityChoices = initChoices('citySelect');
    removeChoices = initChoices('removeSelect');

    loadVisits();
});

Papa.parse("https://raw.githubusercontent.com/datasets/world-cities/master/data/world-cities.csv", {download:true, header:true, complete:function(results){ allCities=results.data; }});

document.getElementById('countrySelect').addEventListener('change', function(){
    var country=this.value; selectedCountryLayer=null;
    countriesLayer.eachLayer(l=>{ if(l.feature.properties.name===country) selectedCountryLayer=l; });
    var citySelect=document.getElementById('citySelect'); citySelect.innerHTML='<option value="">--Select City--</option>';
    allCities.filter(c=>c.country===country).sort((a,b)=>a.name.localeCompare(b.name)).forEach(c=>{
        var opt=document.createElement('option'); opt.value=c.name; opt.text=c.name; citySelect.appendChild(opt);
    });
    cityChoices.destroy(); cityChoices = initChoices('citySelect');
});

// ---------------- Functions ----------------
function markVisited(){
    var color=document.getElementById('colorInput').value;
    var country=document.getElementById('countrySelect').value;
    var city=document.getElementById('citySelect').value;
    if(!country) return;

    if(!city){
        if(selectedCountryLayer) selectedCountryLayer.setStyle({fillColor:color, fillOpacity:0.7});
        saveVisit({user_id:user, country:country, city:'', color:color, full_country:true});
        return;
    }

    saveVisit({user_id:user, country:country, city:city, color:color, full_country:false});

    fetch(`https://nominatim.openstreetmap.org/search?city=${city}&country=${country}&format=json&limit=1`)
    .then(r=>r.json()).then(data=>{
        if(data.length>0){
            var coords=[parseFloat(data[0].lat),parseFloat(data[0].lon)];
            var key=city+","+country;
            if(cityMarkers[key]) map.removeLayer(cityMarkers[key]);
            cityMarkers[key]=L.circleMarker(coords,{radius:6, fillColor:color, color:'#000', weight:1, fillOpacity:0.8})
                            .addTo(map).bindPopup(city+","+country);
            map.setView(coords,7);
        }
    });
}

function saveVisit(data){
    fetch("/save",{method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)})
    .then(r=>r.json()).then(_=>{ showToast("Saved!"); loadVisits(); });
}

function removeVisit(){
    var selected=document.getElementById('removeSelect').value;
    if(!selected) return;
    var parts=selected.split(":"); var country=parts[0]; var city=parts[1]||"";
    fetch("/remove",{method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({user_id:user, country:country, city:city})})
    .then(r=>r.json()).then(_=>{
        if(city){
            var key=city+","+country; 
            if(cityMarkers[key]){ map.removeLayer(cityMarkers[key]); delete cityMarkers[key]; }
        } else {
            countriesLayer.eachLayer(l=>{ if(l.feature.properties.name===country) l.setStyle({fillColor:'white', fillOpacity:0.3}); });
        }
        loadVisits(); showToast("Removed!");
    });
}

document.getElementById('resetBtn').addEventListener('click', function(){
    if(!confirm("Are you sure you want to reset all your records?")) return;
    fetch("/reset",{method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({user_id:user})})
    .then(r=>r.json()).then(_=>{
        for(var key in cityMarkers){ map.removeLayer(cityMarkers[key]); }
        cityMarkers={};
        countriesLayer.eachLayer(l=>{ l.setStyle({fillColor:'white', fillOpacity:0.3}); });
        loadVisits(); showToast("All records reset!");
    });
});

function loadVisits(){
    fetch("/visits/"+user).then(r=>r.json()).then(visits=>{
        visits.forEach(v=>{
            if(!v.city){
                countriesLayer.eachLayer(l=>{ if(l.feature.properties.name===v.country) l.setStyle({fillColor:v.color, fillOpacity:0.7}); });
            } else {
                fetch(`https://nominatim.openstreetmap.org/search?city=${v.city}&country=${v.country}&format=json&limit=1`)
                .then(res=>res.json()).then(data=>{
                    if(data.length>0){
                        var coords=[parseFloat(data[0].lat),parseFloat(data[0].lon)];
                        var key=v.city+","+v.country;
                        if(cityMarkers[key]) map.removeLayer(cityMarkers[key]);
                        cityMarkers[key]=L.circleMarker(coords,{radius:6, fillColor:v.color, color:'#000', weight:1, fillOpacity:0.8})
                                         .addTo(map).bindPopup(v.city+","+v.country);
                    }
                });
            }
        });
        updateRemoveDropdown(visits);
    });
}

function updateRemoveDropdown(visits){
    var removeSelect=document.getElementById('removeSelect'); removeSelect.innerHTML='<option value="">--Select visited--</option>';
    visits.forEach(v=>{
        var key=v.country + (v.city ? ":" + v.city : "");
        var opt=document.createElement('option'); opt.value=key; opt.text=key; removeSelect.appendChild(opt);
    });
    if(removeChoices){ removeChoices.destroy(); removeChoices = initChoices('removeSelect'); }
}
</script>

</body>
</html>
"""

# ---------------- DB ----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS visits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, country TEXT, city TEXT, color TEXT, full_country INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------- ROUTES ----------------
@app.route("/", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username = request.form.get("username","").strip()
        if username:
            session['username'] = username
            return redirect(url_for('map_page'))
    return render_template_string(login_template)

@app.route("/map")
def map_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template_string(map_template, user=session['username'])

@app.route("/save", methods=["POST"])
def save_visit():
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO visits(user_id,country,city,color,full_country) VALUES (?,?,?,?,?)",
              (data.get("user_id"), data.get("country"), data.get("city"), data.get("color"), int(data.get("full_country"))))
    conn.commit(); conn.close()
    return jsonify({"status":"success"})

@app.route("/remove", methods=["POST"])
def remove_visit():
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if data.get("city"):
        c.execute("DELETE FROM visits WHERE user_id=? AND country=? AND city=?",
                  (data.get("user_id"), data.get("country"), data.get("city")))
    else:
        c.execute("DELETE FROM visits WHERE user_id=? AND country=? AND full_country=1",
                  (data.get("user_id"), data.get("country")))
    conn.commit(); conn.close()
    return jsonify({"status":"success"})

@app.route("/reset", methods=["POST"])
def reset_db():
    data = request.json
    user_id = data.get("user_id")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM visits WHERE user_id=?", (user_id,))
    conn.commit(); conn.close()
    return jsonify({"status":"success"})

@app.route("/visits/<user_id>")
def get_visits(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT country,city,color,full_country FROM visits WHERE user_id=?", (user_id,))
    rows = c.fetchall(); conn.close()
    return jsonify([{"country":r[0],"city":r[1],"color":r[2],"full_country":bool(r[3])} for r in rows])

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
