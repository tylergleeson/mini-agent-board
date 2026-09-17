"""Tiny helper for writing SenseCraft HMI layouts by hand. Run: python3 build_layout.py > design.json"""
import json, itertools
_n = itertools.count(1789540000000)
def _id(t): return f"{t}-{next(_n)}"
P = "__device_container_group__"
def rect(x,y,w,h,fill="#ffffff",stroke="transparent",sw=0,r=0):
    return {"type":"rectangle","id":_id("rectangle"),"x":x,"y":y,"width":w,"height":h,"fill":fill,"stroke":stroke,"strokeWidth":sw,"cornerRadius":r,"rotation":0,"parentId":P}
def text(x,y,w,h,value,size=24,color="#000000",align="left",bold=False,font="Montserrat"):
    return {"type":"text","id":_id("text"),"x":x,"y":y,"width":w,"height":h,"value":value,"color":color,"fontFamily":font,"fontSize":size,"fontStyle":"bold" if bold else "normal","textAlign":align,"widthMode":"fixed","rotation":0,"parentId":P}
def clock(x,y,w,h,fmt="h:mm A",tz="America/New_York",size=90,color="#000000",align="center",bold=True,kind="time"):
    e=text(x,y,w,h,"12:00",size,color,align,bold); e["type"]="date"; e["id"]=_id(kind)
    e["dataTransform"]={"type":kind,"options":{"format":fmt,"timezone":tz}}; return e
WEATHER = ("https://sensecraft-hmi-api.seeed.cc/proxy/weather?latitude=38.9097&longitude=-77.0434"
           "&timezone=America%2FNew_York&timeformat=unixtime&forecast_days=5"
           "&current=temperature_2m%2Capparent_temperature%2Crelative_humidity_2m%2Cweather_code%2Cwind_speed_10m"
           "&daily=weather_code%2Ctemperature_2m_max%2Ctemperature_2m_min%2Csunrise%2Csunset")
def data(x,y,w,h,key,label,transform=None,size=24,color="#000000",align="left",bold=False,platform="weather",url=WEATHER,value="--"):
    e=text(x,y,w,h,value,size,color,align,bold); e["type"]="data"; e["id"]=_id("data")
    e.update({"label":label,"requiredPlatform":platform,"dataUrl":url,"dataHeaders":{},"dataKey":key,"sanitizedFields":["dataHeaders.api-key"]})
    if platform=="weather": e["temperatureUnit"]="celsius"
    if transform: e["dataTransform"]=transform
    return e
F = {"type":"custom","options":{"customFunction":"return value == null ? '--' : Math.round(value*9/5+32) + '°';"}}
def icon(x,y,s,key="current.weather_code"):
    return {"type":"data","id":_id("weather_icon"),"x":x,"y":y,"width":s,"height":s,"dataKey":key,"dataUrl":WEATHER,"dataHeaders":{},"requiredPlatform":"weather","sanitizedFields":["dataHeaders.api-key"],"dataTransform":{"type":"weatherIcon","outputType":"image"},"value":"3","rotation":0,"parentId":P}
def layout(children,w=800,h=480,dither=3):
    return {"dither":dither,"stageSize":{"width":1600,"height":900},"stageElements":[{"id":P,"type":"group","x":100,"y":100,"width":w,"height":h,"canvasRotation":0,"children":children}]}

if __name__=="__main__":
    DEV="https://sensecraft-hmi-api.seeed.cc/api/v1/user/device/iot_data/20233536"
    c=[]
    c.append(rect(0,0,800,480,"#ffffff"))
    # left: time/date block
    c.append(rect(0,0,440,480,"#ffffff"))
    c.append(clock(20,40,400,120,"h:mm A",size=110))
    c.append(clock(20,170,400,40,"dddd",kind="date",size=30,bold=False))
    c.append(clock(20,212,400,40,"MMMM D, YYYY",kind="date",size=26,bold=False,color="#666666"))
    c.append(rect(20,275,400,4,"#000000"))
    # today's high/low + sunrise/sunset
    c.append(text(20,300,120,30,"HIGH",16,"#666666"))
    c.append(data(20,326,120,50,"daily.temperature_2m_max.0","Today - High (°F)",F,40,"#ff0000",bold=True))
    c.append(text(150,300,120,30,"LOW",16,"#666666"))
    c.append(data(150,326,120,50,"daily.temperature_2m_min.0","Today - Low (°F)",F,40,"#0000ff",bold=True))
    c.append(text(290,300,130,30,"SUNSET",16,"#666666"))
    c.append(data(290,326,130,50,"daily.sunset.0","Sunset",{"type":"time","options":{"format":"h:mm A","timezone":"America/New_York"}},32,bold=True))
    # right: weather card
    c.append(rect(440,0,360,480,"#ffff00"))
    c.append(text(470,30,300,30,"DUPONT CIRCLE",18,"#000000",bold=True))
    c.append(icon(470,70,150))
    c.append(data(620,90,160,100,"current.temperature_2m","Current - Temperature (°F)",F,72,align="right",bold=True))
    c.append(data(470,240,300,30,"current.apparent_temperature","Feels like",{"type":"custom","options":{"customFunction":"return value == null ? '' : 'Feels like ' + Math.round(value*9/5+32) + '°';"}},20))
    c.append(data(470,272,300,30,"current.relative_humidity_2m","Humidity",{"type":"custom","options":{"customFunction":"return 'Humidity ' + Math.round(value) + '%';"}},20))
    c.append(data(470,304,300,30,"current.wind_speed_10m","Wind",{"type":"custom","options":{"customFunction":"return 'Wind ' + Math.round(value*0.621) + ' mph';"}},20))
    # 3-day strip
    for i,dx in enumerate((470,570,670)):
        c.append(data(dx,360,90,24,f"daily.time.{i+1}","Day",{"type":"date","options":{"format":"ddd","timezone":"America/New_York"}},18,bold=True,align="center"))
        c.append(icon(dx+20,386,50,f"daily.weather_code.{i+1}"))
        c.append(data(dx,440,90,24,f"daily.temperature_2m_max.{i+1}","Hi",F,18,align="center"))
    # battery, bottom-left
    c.append(data(20,440,200,24,"result.battery.level","Battery",{"type":"custom","options":{"customFunction":"return 'Battery ' + value + '%';"}},14,"#666666",platform="device",url=DEV))
    c[-1]["sanitizedFields"]=[]
    print(json.dumps(layout(c),indent=2))
