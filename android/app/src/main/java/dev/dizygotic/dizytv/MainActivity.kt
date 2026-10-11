package dev.dizygotic.dizytv

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject
import org.videolan.libvlc.LibVLC
import org.videolan.libvlc.Media
import org.videolan.libvlc.MediaPlayer
import org.videolan.libvlc.util.VLCVideoLayout
import java.io.File
import java.time.Instant
import java.time.ZoneId
import java.util.concurrent.Executors

class MainActivity:Activity() {
    private lateinit var store:DeviceStore; private lateinit var body:LinearLayout; private lateinit var status:TextView
    private lateinit var zoneLabel:TextView; private lateinit var lib:LibVLC; private lateinit var player:MediaPlayer
    private var video:VLCVideoLayout?=null; private var selected:JSONObject?=null; private var page="Channels"
    private var search=""; private var onlyFavourites=false; private var refreshing=false; private var guide=JSONObject().put("names",JSONObject()).put("programmes",JSONArray())
    private var countryFilter=""; private var genreFilter=""; private var typeFilter=""
    private var sourceErrors=emptyList<String>()
    private var displayedZone=""
    // XMLTV guide may have tens of thousands of programmes. Build grouping
    // only once per freshly imported guide, not on every keypress or page.
    private var indexedGuide:JSONObject?=null
    private var indexedProgrammes:Map<String,List<JSONObject>> = emptyMap()
    private var indexedGenres:Map<String,Set<String>> = emptyMap()
    private fun indexGuide() {
        if(indexedGuide===guide) return
        val grouped=Domain.objects(guide.getJSONArray("programmes")).groupBy { it.getString("channel") }
        indexedProgrammes=grouped
        indexedGenres=grouped.mapValues { (_,rows)->
            rows.flatMap { Domain.strings(it.optJSONArray("categories")?:JSONArray()).map(Domain::normaliseGenre) }.toSet()
        }
        indexedGuide=guide
    }
    private val executor=Executors.newSingleThreadExecutor(); private val handler=Handler(Looper.getMainLooper())
    private val ticker=object:Runnable { override fun run() { val changed=updateZone(); if(page=="Recordings" || changed && page=="Guide") render(); handler.postDelayed(this,5000) } }
    private fun dp(n:Int)=(n*resources.displayMetrics.density).toInt()
    private fun text(value:String,size:Float=15f)=TextView(this).apply { text=value; textSize=size; setTextColor(Color.rgb(243,234,213)); setPadding(dp(10),dp(8),dp(10),dp(8)) }
    private fun button(label:String,action:()->Unit)=Button(this).apply { text=label; setOnClickListener { attempt(action) } }
    private fun row()=LinearLayout(this).apply { orientation=LinearLayout.HORIZONTAL }
    private fun attempt(action:()->Unit) { try { action() } catch(e:Exception) { error(e.message?:e.javaClass.simpleName) } }
    private fun error(message:String) { status.text=message; AlertDialog.Builder(this).setTitle("DizyTV").setMessage(message).setPositiveButton("OK",null).show() }
    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState); store=DeviceStore(this); lib=LibVLC(this,arrayListOf("--no-video-title-show","--network-caching=1500")); player=MediaPlayer(lib)
        val root=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setBackgroundColor(Color.rgb(21,32,25)); setPadding(dp(8),dp(8),dp(8),dp(8)) }
        val brand=row(); val image=ImageView(this); image.setImageResource(R.drawable.dizytv_logo); brand.addView(image,LinearLayout.LayoutParams(dp(64),dp(64))); brand.addView(text("DizyTV",28f)); root.addView(brand)
        zoneLabel=text(""); root.addView(zoneLabel)
        val nav=HorizontalScrollView(this); val buttons=row()
        for(name in listOf("Channels","Live","Guide","Recordings","Backup","Settings")) buttons.addView(button(name) { page=name; render() })
        nav.addView(buttons); root.addView(nav)
        body=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL }; root.addView(body,LinearLayout.LayoutParams(-1,0,1f))
        status=text("Native alpha • Install/open Ace Stream, configure XMLTV and choose recording storage",12f); root.addView(status); setContentView(root)
        runCatching { val file=File(filesDir,"guide.json"); if(file.exists() && file.length()<=100*1024*1024) guide=JSONObject(file.readText()) }
        render(); if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS),20)
        // Import newly added free playlists on upgrades even if old Ace entries were cached.
        refreshChannels()
    }
    override fun onResume() { super.onResume(); attempt { Scheduler.recover(this) }; handler.post(ticker) }
    override fun onPause() { handler.removeCallbacks(ticker); super.onPause() }
    override fun onDestroy() { handler.removeCallbacks(ticker); player.stop(); player.detachViews(); player.release(); lib.release(); executor.shutdown(); super.onDestroy() }
    private fun updateZone():Boolean {
        val zone=store.read().getJSONObject("settings").getString("timezone")
        val effective=Domain.zone(zone); val key=effective.id+effective.rules.getOffset(Instant.now()).id; val changed=key!=displayedZone; displayedZone=key
        zoneLabel.text=(if(zone=="auto") "Auto: ${ZoneId.systemDefault().id}" else zone)+" • "+Domain.time(Instant.now().epochSecond,zone,true)
        return changed
    }
    private fun scroller():LinearLayout { val scroll=ScrollView(this); val column=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL }; scroll.addView(column); body.addView(scroll,LinearLayout.LayoutParams(-1,-1)); return column }
    private fun filteredChannels(state:JSONObject):List<JSONObject> {
        indexGuide()
        val fav=Domain.strings(state.getJSONArray("favourites")); val programmeGenres=indexedGenres
        return Domain.catalogue(state).filter { ch->
            val key=Domain.matchGuide(ch,state.getJSONObject("mappings"),guide.getJSONObject("names"))
            (ch.getString("name")+" "+ch.getString("group")).contains(search,true) && (!onlyFavourites || ch.getString("id") in fav) &&
            (countryFilter.isEmpty() || ch.optString("country","Unspecified")==countryFilter) &&
            (genreFilter.isEmpty() || ch.optString("genre","Unspecified")==genreFilter || genreFilter in programmeGenres[key].orEmpty()) &&
            (typeFilter.isEmpty() || typeFilter in listOf(ch.optString("kind","TV"),ch.optString("transport",if(ch.getString("stream").startsWith("acestream:")) "Ace Stream" else "HTTP")))
        }
    }
    private fun categoryFilters(onChange:()->Unit):LinearLayout {
        val column=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL }; val channels=Domain.catalogue(store.read())
        indexGuide()
        val guideGenres=indexedGenres.values.flatMap { it }
        for(key in listOf("country","genre","kind")) {
            val values=(channels.map { it.optString(key,if(key=="kind") "TV" else "Unspecified") }+if(key=="genre") guideGenres else if(key=="kind") channels.map { it.optString("transport",if(it.getString("stream").startsWith("acestream:")) "Ace Stream" else "HTTP") } else emptyList()).distinct().sorted()
            val label=when(key) { "country"->"All countries"; "genre"->"All genres"; else->"All stream types" }; val options=listOf(label)+values
            val spinner=Spinner(this); spinner.adapter=ArrayAdapter(this,android.R.layout.simple_spinner_dropdown_item,options)
            val current=when(key) { "country"->countryFilter; "genre"->genreFilter; else->typeFilter }; spinner.setSelection(maxOf(0,options.indexOf(current)))
            spinner.onItemSelectedListener=object:AdapterView.OnItemSelectedListener {
                override fun onNothingSelected(parent:AdapterView<*>?){}
                override fun onItemSelected(parent:AdapterView<*>?,view:View?,position:Int,id:Long) {
                    val value=if(position==0) "" else options[position]; val old=when(key) { "country"->countryFilter; "genre"->genreFilter; else->typeFilter }
                    if(old==value) return
                    when(key) { "country"->countryFilter=value; "genre"->genreFilter=value; else->typeFilter=value }; onChange()
                }
            }; column.addView(spinner)
        }; return column
    }
    private fun render() {
        player.detachViews(); video=null; body.removeAllViews(); updateZone()
        when(page) { "Channels"->channels(); "Live"->live(); "Guide"->guidePage(); "Recordings"->recordings(); "Backup"->backupPage(); "Settings"->settingsPage() }
    }
    private fun channels() {
        val input=EditText(this).apply { hint="Search channels or groups"; setText(search); setSingleLine(true) }; body.addView(input)
        val filter=CheckBox(this).apply { text="★ Favourites only"; isChecked=onlyFavourites }; body.addView(filter)
        val refresh=button("Refresh channel catalogue") { refreshChannels() }; body.addView(refresh)
        body.addView(button("Source counts / import errors") {
            val s=store.read()
            val counts=Domain.objects(s.getJSONArray("channels")).groupingBy { it.optString("source",Sources.legacy) }.eachCount()
            val lines=Sources.urls(s.getJSONObject("settings")).map { "${Sources.label(it)}: ${counts[it]?:0} saved channels" }
            AlertDialog.Builder(this).setTitle("DizyTV playlist sources")
                .setMessage((lines+listOf("Refresh channels to update these counts.")+sourceErrors).joinToString("\n"))
                .setPositiveButton("OK",null).show()
        })
        val list=ListView(this); body.addView(list,LinearLayout.LayoutParams(-1,0,1f)); var shown=listOf<JSONObject>()
        fun populate() {
            val state=store.read(); val fav=Domain.strings(state.getJSONArray("favourites")).toSet()
            shown=filteredChannels(state)
            list.adapter=ArrayAdapter(this,android.R.layout.simple_list_item_1,shown.map { (if(it.getString("id") in fav) "★ " else "")+it.getString("name") })
        }
        body.addView(categoryFilters { populate() },2)
        input.addTextChangedListener(object:TextWatcher { override fun beforeTextChanged(s:CharSequence?,start:Int,count:Int,after:Int){}; override fun onTextChanged(s:CharSequence?,start:Int,before:Int,count:Int) { search=s.toString(); populate() }; override fun afterTextChanged(s:Editable?){} })
        filter.setOnCheckedChangeListener { _,checked->onlyFavourites=checked; populate() }
        list.setOnItemClickListener { _,_,position,_->selected=shown[position]; page="Live"; render(); play() }
        list.setOnItemLongClickListener { _,_,position,_->toggleFavourite(shown[position]); populate(); true }; populate()
    }
    private fun live() {
        body.addView(text(selected?.getString("name")?:"Choose a channel first",20f))
        selected?.let { ch->
            val state=store.read(); val key=state.getJSONObject("mappings").optString(ch.getString("id"),ch.getString("tvg_id")); val now=Instant.now().epochSecond
            indexGuide()
            val programmes=indexedProgrammes[key].orEmpty().filter { it.getLong("end")>now }.sortedBy { it.getLong("start") }.take(2)
            body.addView(text(programmes.joinToString("\n") { Domain.time(it.getLong("start"),state.getJSONObject("settings").getString("timezone"),true)+"  "+it.getString("title") }.ifEmpty { "No guide match — choose Map EPG" }))
        }
        val layout=VLCVideoLayout(this); video=layout; body.addView(layout,LinearLayout.LayoutParams(-1,0,1f)); player.attachViews(layout,null,false,false)
        val controls=row(); controls.addView(button("Play") { play() }); controls.addView(button("Stop playback") { player.stop() }); controls.addView(button("Record now") { recordNow() }); body.addView(controls)
        val more=row(); more.addView(button("★ Favourite") { selected?.let { toggleFavourite(it) } }); more.addView(button("Map EPG") { mapChannel() }); body.addView(more)
        body.addView(button("Edit categories") { editCategories() })
    }
    private fun isLocalEngineAvailable(address:String):Boolean {
        val uri=Uri.parse(address)
        if(uri.host !in listOf("localhost","127.0.0.1","::1")) return true
        return runCatching {
            java.net.Socket().use { socket ->
                socket.connect(java.net.InetSocketAddress(uri.host,if(uri.port>0) uri.port else 6878),500)
            }
            true
        }.getOrDefault(false)
    }
    private fun play()=attempt {
        val ch=selected?:return@attempt; val s=store.read()
        require(Domain.objects(s.getJSONArray("jobs")).none { it.getString("status")=="recording" && it.getString("channel_id")!=ch.getString("id") }) { "Another channel is recording. Finish or stop it before changing playback." }
        val isAce=Domain.aceId(ch.getString("stream"))!=null
        if(isAce && !isLocalEngineAvailable(s.getJSONObject("settings").getString("engine_url"))) {
            val installed=listOf("org.acestream.media","org.acestream.core")
                .firstNotNullOfOrNull { packageManager.getLaunchIntentForPackage(it) }
            if(installed!=null) {
                AlertDialog.Builder(this).setTitle("Ace Stream engine is stopped")
                    .setMessage("This channel needs your installed Ace Stream engine. Open it, then return to DizyTV and press Play. Ordinary HTTP/HLS channels work without it.")
                    .setPositiveButton("Open engine") { _,_-> startActivity(installed) }
                    .setNegativeButton("Cancel",null).show()
            } else {
                error("Ace Stream is not installed on this device. Install the official engine to play Ace channels; HTTP/HLS channels work without it.")
            }
            return@attempt
        }
        val media=Media(lib,Uri.parse(Domain.stream(ch,s.getJSONObject("settings"))))
        player.media=media; media.release(); player.play()
        status.text=if(isAce) "Connecting to Ace engine…" else "Connecting to HTTP/HLS stream…"
        handler.postDelayed({
            if(page=="Live" && player.isPlaying.not())
                status.text="Stream still buffering or unavailable. Try a different channel if it does not play."
        },20000)
    }
    private fun toggleFavourite(ch:JSONObject) {
        store.update { s->val fav=Domain.strings(s.getJSONArray("favourites")).toMutableList(); if(!fav.remove(ch.getString("id"))) fav.add(ch.getString("id")); s.put("favourites",JSONArray(fav)) }
        status.text="Favourite list updated"
    }
    private fun editCategories() {
        val ch=selected?:return; val fields=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(dp(16),0,dp(16),0) }
        val country=EditText(this).apply { hint="Country"; setText(ch.optString("country","Unspecified")); setSingleLine(true) }
        val genre=EditText(this).apply { hint="Genre"; setText(ch.optString("genre","Unspecified")); setSingleLine(true) }
        val kind=Spinner(this); val kinds=listOf("TV","Radio"); kind.adapter=ArrayAdapter(this,android.R.layout.simple_spinner_dropdown_item,kinds); kind.setSelection(maxOf(0,kinds.indexOf(ch.optString("kind","TV"))))
        fields.addView(country); fields.addView(genre); fields.addView(kind)
        fun save(values:JSONObject?)=attempt {
            store.update { s->val overrides=s.optJSONObject("category_overrides")?:JSONObject(); if(values==null) overrides.remove(ch.getString("id")) else overrides.put(ch.getString("id"),values); s.put("category_overrides",overrides) }
            selected=Domain.catalogue(store.read()).firstOrNull { it.getString("id")==ch.getString("id") }; render(); status.text="Categories saved • kept across refresh and backup"
        }
        AlertDialog.Builder(this).setTitle("Edit categories").setView(fields).setNegativeButton("Cancel",null).setNeutralButton("Use source") { _,_->save(null) }.setPositiveButton("Save") { _,_->save(JSONObject().put("country",country.text.toString().trim().ifEmpty { "Unspecified" }).put("genre",Domain.normaliseGenre(genre.text.toString())).put("kind",kinds[kind.selectedItemPosition])) }.show()
    }
    private fun mapChannel() {
        val ch=selected?:return; val names=guide.getJSONObject("names"); val keys=names.keys().asSequence().sorted().toList()
        AlertDialog.Builder(this).setTitle("Map ${ch.getString("name")}").setItems((listOf("No mapping")+keys.map { "$it — ${names.getString(it)}" }).toTypedArray()) { _,position->
            store.update { it.getJSONObject("mappings").put(ch.getString("id"),if(position==0) "" else keys[position-1]) }; render()
        }.show()
    }
    private fun guidePage() {
        body.addView(categoryFilters { render() })
        body.addView(text("Tap a programme to watch its channel • long-press to record",13f))
        body.addView(button("Refresh XMLTV guide") { refreshGuide() }); val s=store.read(); val timezone=s.getJSONObject("settings").getString("timezone")
        val start=Instant.now().epochSecond/3600*3600; body.addView(text(Domain.time(start,timezone)+" • next six hours"))
        val outer=ScrollView(this); val horizontal=HorizontalScrollView(this); val grid=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL }
        val headings=row(); headings.addView(text("Channel"),LinearLayout.LayoutParams(dp(140),dp(50)))
        for(i in 0..5) headings.addView(text(Domain.time(start+i*3600,timezone,true)),LinearLayout.LayoutParams(dp(180),dp(50)))
        grid.addView(headings)
        indexGuide()
        val catalogue=filteredChannels(s).take(250)
        for(ch in catalogue) {
            val r=row()
            val channelName=text(ch.getString("name"))
            channelName.setOnClickListener { selected=ch; page="Live"; render(); play() }
            channelName.setOnLongClickListener { selected=ch; recordNow(); true }
            r.addView(channelName,LinearLayout.LayoutParams(dp(140),dp(68)))
            val timeline=android.widget.FrameLayout(this); r.addView(timeline,LinearLayout.LayoutParams(dp(1080),dp(68)))
            val key=Domain.matchGuide(ch,s.getJSONObject("mappings"),guide.getJSONObject("names"))
            val programmes=indexedProgrammes[key].orEmpty().filter { it.getLong("end")>start && it.getLong("start")<start+21600 && (genreFilter.isEmpty() || ch.optString("genre","Unspecified")==genreFilter || genreFilter in Domain.strings(it.optJSONArray("categories")?:JSONArray()).map(Domain::normaliseGenre)) }
            if(programmes.isEmpty()) timeline.addView(text("No guide match — choose Map EPG"))
            for(p in programmes) {
                val left=maxOf(p.getLong("start"),start)-start; val width=minOf(p.getLong("end"),start+21600)-maxOf(p.getLong("start"),start)
                val b=button(p.getString("title")) { selected=ch; page="Live"; render(); play() }
                b.setOnLongClickListener { attempt { scheduleProgramme(ch,p) }; true }
                b.textSize=12f
                val params=android.widget.FrameLayout.LayoutParams(maxOf(dp(20),dp((width*180/3600).toInt())),dp(64)); params.leftMargin=dp((left*180/3600).toInt()); timeline.addView(b,params)
            }
            grid.addView(r)
        }
        horizontal.addView(grid); outer.addView(horizontal); body.addView(outer,LinearLayout.LayoutParams(-1,0,1f))
    }
    private fun storageChosen():Boolean {
        val uri=Uri.parse(store.read().getJSONObject("settings").getString("recording_dir"))
        return uri.scheme=="content" && contentResolver.persistedUriPermissions.any { it.uri==uri && it.isWritePermission }
    }
    private fun addJob(job:JSONObject) {
        require(storageChosen()) { "Choose a recording folder in Settings first" }
        if(!Scheduler.exactAllowed(this)) {
            if(Build.VERSION.SDK_INT>=31) startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,Uri.parse("package:$packageName")))
            throw IllegalArgumentException("Grant exact-alarm access, then schedule this recording again")
        }
        store.update { s->require(Domain.objects(s.getJSONArray("jobs")).none { Domain.overlap(it,job) }) { "This timer overlaps another recording including padding" }; s.getJSONArray("jobs").put(job) }
        try { Scheduler.arm(this,job) } catch(e:Exception) { store.job(job.getString("id")) { it.put("status","paused").put("error",e.message) }; throw e }
        status.text="Recording timer saved"; page="Recordings"; render()
    }
    private fun recordNow() {
        val ch=selected?:return
        val options=arrayOf("30 minutes","60 minutes","120 minutes","Until current programme ends","Until stopped (maximum 24 hours)")
        AlertDialog.Builder(this).setTitle("Record now").setItems(options) { _,index->attempt {
            val now=Instant.now().epochSecond; var end=now+listOf(1800L,3600L,7200L,86400L,86400L)[index]; var title=ch.getString("name")
            if(index==3) {
                val s=store.read(); val key=Domain.matchGuide(ch,s.getJSONObject("mappings"),guide.getJSONObject("names"))
                val p=Domain.objects(guide.getJSONArray("programmes")).firstOrNull { it.getString("channel")==key && it.getLong("start")<=now && now<it.getLong("end") }?:throw IllegalArgumentException("No current programme mapped")
                end=p.getLong("end")+s.getJSONObject("settings").getInt("padding_after")*60; title=p.getString("title")
            }
            addJob(Domain.job(ch.getString("id"),title,now,end,0,0))
        } }.show()
    }
    private fun scheduleProgramme(ch:JSONObject,p:JSONObject) {
        val settings=store.read().getJSONObject("settings"); val zone=settings.getString("timezone")
        require(p.getLong("end")>Instant.now().epochSecond) { "This programme has ended" }
        AlertDialog.Builder(this).setTitle("Record ${p.getString("title")}").setMessage(ch.getString("name")+"\n"+Domain.time(p.getLong("start"),zone)+"\n"+Domain.time(p.getLong("end"),zone)+"\nPadding: ${settings.getInt("padding_before")}m before / ${settings.getInt("padding_after")}m after").setNegativeButton("Cancel",null).setPositiveButton("Schedule") { _,_->attempt { addJob(Domain.job(ch.getString("id"),p.getString("title"),p.getLong("start"),p.getLong("end"),settings.getInt("padding_before"),settings.getInt("padding_after"))) } }.show()
    }
    private fun recordings() {
        val list=scroller(); val s=store.read(); val zone=s.getJSONObject("settings").getString("timezone")
        list.addView(text("One recording at a time • device storage only\nForce-stop, missing engine or revoked permissions can prevent timers from running.",13f))
        for(j in Domain.objects(s.getJSONArray("jobs")).sortedByDescending { it.getLong("start") }) {
            list.addView(text(j.getString("title")+"\n"+Domain.time(j.getLong("start"),zone)+"\n"+j.getString("status")+" • ${j.optLong("bytes")/1024/1024} MiB\n"+j.optString("error")))
            val controls=row(); val id=j.getString("id")
            if(j.getString("status") in Domain.active+"paused") controls.addView(button("Stop / cancel") { Scheduler.cancel(this,id); store.job(id) { it.put("status","cancelled") }; if(j.getString("status")=="recording") startService(Intent(this,RecordingService::class.java).setAction("stop")); render() })
            if(j.getString("status")=="paused") controls.addView(button("Rearm timer") {
                require(storageChosen()) { "Choose recording storage again" }; require(j.getLong("end")>Instant.now().epochSecond) { "Timer expired" }
                require(Domain.objects(store.read().getJSONArray("channels")).any { it.getString("id")==j.getString("channel_id") }) { "Refresh this channel before rearming" }
                store.update { current->require(Domain.objects(current.getJSONArray("jobs")).none { Domain.overlap(it,j) }) { "Timer conflict" }; Domain.objects(current.getJSONArray("jobs")).first { it.getString("id")==id }.put("status","queued") }
                Scheduler.recover(this); render()
            })
            val uris=Domain.recordingUris(j)
            if(uris.isNotEmpty()) {
                controls.addView(button("Play file") {
                    fun play(uri:String) { page="Live"; render(); val media=Media(lib,Uri.parse(uri)); player.media=media; media.release(); player.play() }
                    if(uris.size==1) play(uris[0]) else AlertDialog.Builder(this).setTitle("Preserved recording segments").setItems(uris.mapIndexed { i,_->"Segment ${i+1}" }.toTypedArray()) { _,i->attempt { play(uris[i]) } }.show()
                })
                if(j.getString("status") !in Domain.active) controls.addView(button("Delete file") { AlertDialog.Builder(this).setTitle("Delete this recording and its preserved segments?").setNegativeButton("Cancel",null).setPositiveButton("Delete") { _,_->attempt { uris.forEach { contentResolver.delete(Uri.parse(it),null,null) }; store.update { it.put("jobs",JSONArray(Domain.objects(it.getJSONArray("jobs")).filter { job->job.getString("id")!=id })) }; render() } }.show() })
            }
            list.addView(controls)
        }
    }
    private fun backupPage() {
        val list=scroller(); list.addView(text("Local backup & restore",24f)); list.addView(text("Back up channels, favourites, settings, guide mappings and timers to a JSON file on your device.\n\nVideos and device permissions are excluded. Restored timers stay paused until you choose storage and rearm them."))
        list.addView(button("Save local backup") { startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json").putExtra(Intent.EXTRA_TITLE,"DizyTV-backup.json"),101) })
        list.addView(button("Restore local backup") { startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json"),102) })
    }
    private fun settingsPage() {
        val list=scroller(); val original=store.read().getJSONObject("settings"); val fields=mutableMapOf<String,EditText>()
        fun field(key:String,label:String,value:String) { list.addView(text(label)); val input=EditText(this).apply { setText(value); maxLines=if(key=="xmltv_urls" || key=="playlist_urls") 8 else 1 }; fields[key]=input; list.addView(input) }
        field("playlist_urls","Channel playlists (one URL per line; remove to disable)",Sources.urls(original).joinToString("\n"))
        list.addView(button("Add built-in free playlists") {
            val existing=fields["playlist_urls"]!!.text.lines().map { it.trim() }.filter { it.isNotEmpty() }
            fields["playlist_urls"]!!.setText((existing+Sources.presets).distinct().joinToString("\n"))
        })
        field("engine_url","Ace engine URL",original.getString("engine_url"))
        field("xmltv_urls","XMLTV URLs — one per line",Domain.strings(original.getJSONArray("xmltv_urls")).joinToString("\n"))
        field("timezone","Timezone — auto or IANA name",original.getString("timezone")); list.addView(button("Choose timezone") { val zones=(listOf("auto")+ZoneId.getAvailableZoneIds().sorted()).toTypedArray(); AlertDialog.Builder(this).setTitle("Display timezone").setItems(zones) { _,i->fields["timezone"]!!.setText(zones[i]) }.show() })
        field("epg_offset_minutes","EPG correction in minutes (new imports only)",original.getInt("epg_offset_minutes").toString())
        field("padding_before","Minutes before programme",original.getInt("padding_before").toString()); field("padding_after","Minutes after programme",original.getInt("padding_after").toString())
        field("reserve_bytes","Free-space reserve in bytes",original.getLong("reserve_bytes").toString())
        list.addView(text("Recording folder: "+original.getString("recording_dir").ifEmpty { "Not selected" })); list.addView(button("Choose recording folder") { startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION),100) })
        list.addView(button("Save settings") {
            store.update { state->val settings=state.getJSONObject("settings"); for((key,input) in fields) when(key) {
                "xmltv_urls","playlist_urls"-> {
                    val urls=input.text.lines().map { it.trim() }.filter { it.isNotEmpty() }.distinct()
                    settings.put(key,JSONArray(urls))
                    if(key=="playlist_urls" && urls.isNotEmpty()) settings.put("playlist_url",urls.first())
                }
                "epg_offset_minutes","padding_before","padding_after"->settings.put(key,input.text.toString().toInt())
                "reserve_bytes"->settings.put(key,input.text.toString().toLong())
                else->settings.put(key,input.text.toString().trim())
            } }; status.text="Settings saved • existing UTC timers unchanged"; updateZone()
        })
        list.addView(button("Open installed Ace Stream") { val launch=listOf("org.acestream.media","org.acestream.core").firstNotNullOfOrNull { packageManager.getLaunchIntentForPackage(it) }; require(launch!=null) { "Install/open Ace Stream separately, then return to DizyTV" }; startActivity(launch) })
        list.addView(text("Recording needs an available engine and storage grant. Free space may be unknown for some Android storage providers. Automatic timezone uses the device setting; saved timers stay in UTC.",13f))
    }
    private fun refreshChannels() {
        if(refreshing) return
        val previous=store.read(); refreshing=true; status.text="Importing free channel sources…"
        executor.execute {
            val result=runCatching { Sources.refresh(previous.getJSONObject("settings"),previous.getJSONArray("channels"),Feeds::download) }
            handler.post {
                refreshing=false
                result.onSuccess { refreshed->attempt {
                    sourceErrors=refreshed.errors
                    if(refreshed.succeeded>0) store.update { it.put("channels",refreshed.channels) }
                    status.text="${refreshed.channels.length()} channels • ${refreshed.succeeded} sources updated • ${refreshed.errors.size} failed (cached)"
                    render()
                    if(guide.getJSONArray("programmes").length()==0) refreshGuide()
                } }.onFailure { status.text="Refresh failed; cached channels retained: ${it.message}" }
            }
        }
    }
    private fun refreshGuide() {
        if(refreshing) return; val settings=store.read().getJSONObject("settings"); val urls=Domain.strings(settings.getJSONArray("xmltv_urls")); require(urls.isNotEmpty()) { "Add XMLTV source URLs in Settings" }
        refreshing=true; status.text="Importing XMLTV…"
        executor.execute {
            val result=runCatching {
                val names=JSONObject(); val programmes=JSONArray(); var ok=0; var failed=0
                for(url in urls) {
                    try {
                        val data=Feeds.xmltv(Feeds.download(url),settings.getInt("epg_offset_minutes"))
                        val sourceNames=data.getJSONObject("names")
                        sourceNames.keys().forEach { names.put(it,sourceNames.get(it)) }
                        Domain.objects(data.getJSONArray("programmes")).forEach { programmes.put(it) }
                        ok++
                    } catch(_:Exception) { failed++ }
                }
                require(ok>0) { "All ${urls.size} guide sources failed; cached guide retained" }
                Pair(JSONObject().put("names",names).put("programmes",programmes),failed)
            }
            handler.post {
                refreshing=false
                result.onSuccess { (fresh,failed)->attempt {
                    JsonCache.write(File(filesDir,"guide.json"),fresh.toString())
                    guide=fresh
                    status.text="Imported ${fresh.getJSONArray("programmes").length()} programmes • ${failed} source(s) failed • UTC timers unchanged"
                    render()
                } }.onFailure { status.text="Guide refresh failed; cache retained: ${it.message}" }
            }
        }
    }
    @Deprecated("Native document picker compatibility")
    override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?) {
        super.onActivityResult(requestCode,resultCode,data); if(resultCode!=RESULT_OK) return; val uri=data?.data?:return
        attempt { when(requestCode) {
            100->{
                val required=Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                require((data.flags and required)==required) { "Choose a folder that allows both reading and writing recordings" }
                contentResolver.takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                store.update { it.getJSONObject("settings").put("recording_dir",uri.toString()) }; render()
            }
            101->{ val payload=Domain.backup(store.read()); contentResolver.openOutputStream(uri,"wt")?.use { it.write(payload.toByteArray()) }?:throw IllegalArgumentException("Cannot write backup"); status.text="Backup saved on device" }
            102->{
                val input=contentResolver.openInputStream(uri)?:throw IllegalArgumentException("Cannot read backup"); val out=java.io.ByteArrayOutputStream()
                input.use { val buffer=ByteArray(8192); while(true) { val n=it.read(buffer); if(n<0) break; require(out.size()+n<=Domain.MAX_BACKUP) { "Backup exceeds 16 MiB" }; out.write(buffer,0,n) } }
                val restored=Domain.restore(out.toString("UTF-8")); val current=store.read(); require(Domain.objects(current.getJSONArray("jobs")).none { it.getString("status") in listOf("starting","recording") }) { "Stop active recording before restoring" }
                AlertDialog.Builder(this).setTitle("Restore backup?").setMessage("Replace preferences with ${restored.getJSONArray("channels").length()} channels, ${restored.getJSONArray("favourites").length()} favourites and ${restored.getJSONArray("jobs").length()} timers?\nSelect storage again. Timers remain paused.").setNegativeButton("Cancel",null).setPositiveButton("Restore") { _,_->attempt {
                    store.update { s->require(Domain.objects(s.getJSONArray("jobs")).none { it.getString("status") in listOf("starting","recording") }) { "Stop active recording first" }; Domain.objects(s.getJSONArray("jobs")).forEach { Scheduler.cancel(this,it.getString("id")) }; s.keys().asSequence().toList().forEach { s.remove(it) }; restored.keys().forEach { s.put(it,restored.get(it)) } }
                    guide=JSONObject().put("names",JSONObject()).put("programmes",JSONArray()); File(filesDir,"guide.json").delete(); selected=null; status.text="Backup restored; choose storage and rearm timers"; render()
                } }.show()
            }
        } }
    }
}
