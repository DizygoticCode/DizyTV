package dev.dizygotic.dizytv

/** Outstanding service requests. The single executor preserves arrival order. */
class RecordingQueue {
    private val ids=linkedSetOf<String>()
    @Volatile var latestStartId=0; private set
    @Synchronized fun observe(startId:Int) { latestStartId=startId }
    @Synchronized fun enqueue(id:String,startId:Int):Boolean { latestStartId=startId; return ids.add(id) }
    @Synchronized fun finish(id:String):Boolean { ids.remove(id); return ids.isEmpty() }
    @Synchronized fun size()=ids.size
}
