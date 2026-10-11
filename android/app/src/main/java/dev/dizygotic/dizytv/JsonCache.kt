package dev.dizygotic.dizytv

import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption

object JsonCache {
    fun write(target:File,text:String,replace:(File,File)->Unit={ source,destination->
        Files.move(source.toPath(),destination.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING)
    }) {
        target.parentFile!!.mkdirs(); val temporary=File.createTempFile(target.name+".",".tmp",target.parentFile)
        try { FileOutputStream(temporary).use { it.write(text.toByteArray(Charsets.UTF_8)); it.fd.sync() }; replace(temporary,target) }
        finally { temporary.delete() }
    }
}
