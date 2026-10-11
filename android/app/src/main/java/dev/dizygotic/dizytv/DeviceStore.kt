package dev.dizygotic.dizytv

import android.content.Context
import android.util.AtomicFile
import org.json.JSONObject
import java.io.File

class DeviceStore(context:Context) {
    private val file=AtomicFile(File(context.filesDir,"state.json"))
    companion object { private val lock=Any() }
    fun read():JSONObject=synchronized(lock) {
        if(!file.baseFile.exists()) Domain.defaults() else {
            require(file.baseFile.length()<=Domain.MAX_BACKUP) { "Device state exceeds 16 MiB" }
            Domain.validate(JSONObject(file.openRead().use { it.readBytes().toString(Charsets.UTF_8) }))
        }
    }
    fun update(change:(JSONObject)->Unit):JSONObject=synchronized(lock) {
        val state=read(); change(state); Domain.validate(state)
        val data=state.toString().toByteArray(); require(data.size<=Domain.MAX_BACKUP)
        val out=file.startWrite()
        try { out.write(data); file.finishWrite(out) } catch(e:Exception) { file.failWrite(out); throw e }
        state
    }
    fun job(id:String,change:(JSONObject)->Unit)=update { s->Domain.objects(s.getJSONArray("jobs")).firstOrNull { it.getString("id")==id }?.let(change) }
    fun claim(id:String,now:Long):Pair<JSONObject,JSONObject>? {
        var accepted=false
        val state=update { s->Domain.objects(s.getJSONArray("jobs")).firstOrNull { it.getString("id")==id }?.let { accepted=Domain.claim(it,now) } }
        if(!accepted) return null
        return state to Domain.objects(state.getJSONArray("jobs")).first { it.getString("id")==id }
    }
}
