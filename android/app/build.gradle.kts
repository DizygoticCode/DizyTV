plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "dev.dizygotic.dizytv"
    compileSdk = 36
    defaultConfig {
        applicationId = "dev.dizygotic.dizytv"
        minSdk = 26
        targetSdk = 35
        versionCode = 7
        versionName = "0.1.6-alpha"
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { buildConfig = true }
    packaging { jniLibs { useLegacyPackaging = false } }
    lint { abortOnError = true; checkReleaseBuilds = true }
    sourceSets.getByName("main").assets.srcDirs("../../assets/licenses",layout.buildDirectory.dir("licence-assets"))
}
val copyLicenceNotice by tasks.registering(Copy::class) {
    from("../../THIRD-PARTY-NOTICES.md") { rename { "NOTICES.md" } }
    into(layout.buildDirectory.dir("licence-assets"))
}
tasks.named("preBuild") { dependsOn(copyLicenceNotice) }
dependencies {
    implementation("org.videolan.android:libvlc-all:3.7.5")
    implementation("androidx.documentfile:documentfile:1.0.1")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
