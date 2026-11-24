# Third-party notices

CallShield application code is distributed under Apache License 2.0. Its dependencies remain subject to their respective licenses.

The repository includes Gradle Wrapper bootstrap files copied from the legacy Android project. Gradle is an Apache License 2.0 project; a copy of the license is retained in `docs/licenses/gradle.txt`. The Gradle distribution is downloaded by the wrapper and is not included in the source archive.

Key dependencies and upstream projects:

- [AndroidX Room](https://developer.android.com/jetpack/androidx/releases/room)
- [OkHttp](https://github.com/square/okhttp)
- [FastAPI](https://github.com/fastapi/fastapi)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper), an optional ASR dependency

`uv.lock` records resolved Python dependencies. Android dependency versions are declared in `android/app/build.gradle.kts`. No third-party model weights, runtime databases, or recordings are included in the source archive. Model downloads and bundled APK dependencies retain their upstream terms.
