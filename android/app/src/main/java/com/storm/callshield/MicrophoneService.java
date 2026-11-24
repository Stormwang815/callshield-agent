package com.storm.callshield;
import android.app.*;
import android.content.*;
import android.media.*;
import android.os.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.*;

/** User-started microphone capture. Does not claim privileged call-audio access. */
public class MicrophoneService extends Service {
  private final ExecutorService io = Executors.newSingleThreadExecutor();
  private final AtomicBoolean active = new AtomicBoolean();
  private volatile AudioRecord recorder;
  private final Set<Integer> seen = new HashSet<>();
  private android.telephony.TelephonyManager phone;
  private android.telephony.PhoneStateListener listener;
  private boolean observedOffhook;
  @Override
  public void onCreate() {
    super.onCreate();
    if (checkSelfPermission(android.Manifest.permission.READ_PHONE_STATE)
        == android.content.pm.PackageManager.PERMISSION_GRANTED) {
      phone = getSystemService(android.telephony.TelephonyManager.class);
      listener = new android.telephony.PhoneStateListener() {
        @Override
        public void onCallStateChanged(int state, String ignored) {
          if (state == android.telephony.TelephonyManager.CALL_STATE_OFFHOOK)
            observedOffhook = true;
          if (state == android.telephony.TelephonyManager.CALL_STATE_IDLE && observedOffhook)
            stopCapture();
        }
      };
      try {
        phone.listen(listener, android.telephony.PhoneStateListener.LISTEN_CALL_STATE);
      } catch (SecurityException ignored) {
      }
    }
  }
  @Override
  public IBinder onBind(Intent i) {
    return null;
  }
  @Override
  public int onStartCommand(Intent intent, int flags, int startId) {
    if (intent == null || "STOP".equals(intent.getAction())) {
      stopCapture();
      stopSelf();
      return START_NOT_STICKY;
    }
    if (!active.compareAndSet(false, true))
      return START_NOT_STICKY;
    Alerts.channels(this);
    PendingIntent stop = PendingIntent.getService(this, 0,
        new Intent(this, MicrophoneService.class).setAction("STOP"),
        PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    Notification n = new Notification.Builder(this, Alerts.MIC)
                         .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                         .setContentTitle("Microphone analysis in progress")
                         .setContentText("User-started, up to 60 seconds. Tap to stop.")
                         .setContentIntent(stop)
                         .setOngoing(true)
                         .build();
    try {
      startForeground(1, n);
    } catch (Exception e) {
      active.set(false);
      stopSelf();
      return START_NOT_STICKY;
    }
    String number = intent.getStringExtra("number");
    io.execute(() -> capture(number));
    return START_NOT_STICKY;
  }
  private void capture(String number) {
    String id = UUID.randomUUID().toString();
    int index = 0;
    Backend backend = null;
    boolean initialized = false, failed = false;
    var settings = getSharedPreferences("settings", 0);
    try {
      backend = new Backend(this);
      backend.json("POST", "/v1/calls/init",
          new JSONObject()
              .put("call_id", id)
              .put("upload_consent", true)
              .put("number_context", Backend.numberContext(this, number)));
      initialized = true;
      settings.edit()
          .putString("last_call", id)
          .putString("last_status", "Capturing audio. Call ID: " + id)
          .apply();
      int min = AudioRecord.getMinBufferSize(
          16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
      if (min <= 0)
        throw new IOException("This device does not support the required audio format");
      if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
          != android.content.pm.PackageManager.PERMISSION_GRANTED)
        throw new SecurityException("Microphone permission has not been granted");
      recorder = new AudioRecord(MediaRecorder.AudioSource.MIC, 16000, AudioFormat.CHANNEL_IN_MONO,
          AudioFormat.ENCODING_PCM_16BIT, Math.max(min * 2, 4096));
      if (recorder.getState() != AudioRecord.STATE_INITIALIZED)
        throw new IOException("Microphone initialization failed");
      long deadline = SystemClock.elapsedRealtime() + 60000;
      byte[] buffer = new byte[3200];
      while (active.get() && SystemClock.elapsedRealtime() < deadline && index < 6) {
        recorder.startRecording();
        ByteArrayOutputStream pcm = new ByteArrayOutputStream();
        long end = Math.min(deadline, SystemClock.elapsedRealtime() + 10000);
        while (active.get() && SystemClock.elapsedRealtime() < end && pcm.size() < 320000) {
          int read = recorder.read(buffer, 0, Math.min(buffer.length, 320000 - pcm.size()));
          if (read <= 0) {
            if (!active.get())
              break;
            throw new IOException("Microphone read failed");
          }
          pcm.write(buffer, 0, read);
        }
        try {
          recorder.stop();
        } catch (Exception ignored) {
        }
        if (pcm.size() < 6400)
          break;
        File wav = File.createTempFile("segment-", ".wav", getCacheDir());
        try {
          writeWav(wav, pcm.toByteArray());
          backend.upload(id, index++, wav);
          poll(backend, id, number);
        } finally {
          wav.delete();
        }
      }
    } catch (Exception e) {
      failed = true;
      settings.edit()
          .putString("last_status",
              "Analysis did not complete: "
                  + (e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()))
          .apply();
    } finally {
      active.set(false);
      releaseRecorder();
      if (initialized && backend != null) {
        boolean done = false;
        for (int attempt = 0; attempt < 6; attempt++) try {
            JSONObject alerts = poll(backend, id, number);
            if (alerts.optInt("pending", 0) > 0) {
              Thread.sleep(2000);
              continue;
            }
            JSONObject summary = backend.json("POST", "/v1/calls/" + id + "/finalize",
                new JSONObject().put("confirmed_spam", false));
            if (!failed)
              settings.edit()
                  .putString("last_status", Backend.summaryText(summary.getJSONObject("summary")))
                  .apply();
            done = true;
            break;
          } catch (Exception ignored) {
            try {
              Thread.sleep(1000);
            } catch (InterruptedException interrupted) {
              Thread.currentThread().interrupt();
              break;
            }
          }
        if (!done && !failed)
          settings.edit()
              .putString(
                  "last_status", "Capture ended; backend results are not ready. Call ID: " + id)
              .apply();
      }
      stopForeground(STOP_FOREGROUND_REMOVE);
      stopSelf();
    }
  }
  private JSONObject poll(Backend b, String id, String number) throws Exception {
    JSONObject r = b.json("GET", "/v1/calls/" + id + "/alerts", null);
    JSONArray list = r.optJSONArray("alerts");
    if (list != null)
      for (int i = 0; i < list.length(); i++) {
        JSONObject item = list.getJSONObject(i);
        if (seen.add(item.getInt("segment_id")))
          Backend.applyResult(this, number, id, item);
      }
    return r;
  }
  private void stopCapture() {
    active.set(false);
    AudioRecord r = recorder;
    if (r != null)
      try {
        r.stop();
      } catch (Exception ignored) {
      }
  }
  private void releaseRecorder() {
    AudioRecord r = recorder;
    recorder = null;
    if (r != null) {
      try {
        r.stop();
      } catch (Exception ignored) {
      }
      r.release();
    }
  }
  private static void writeWav(File file, byte[] pcm) throws IOException {
    try (DataOutputStream o = new DataOutputStream(new FileOutputStream(file))) {
      o.writeBytes("RIFF");
      little(o, 36 + pcm.length, 4);
      o.writeBytes("WAVEfmt ");
      little(o, 16, 4);
      little(o, 1, 2);
      little(o, 1, 2);
      little(o, 16000, 4);
      little(o, 32000, 4);
      little(o, 2, 2);
      little(o, 16, 2);
      o.writeBytes("data");
      little(o, pcm.length, 4);
      o.write(pcm);
    }
  }
  private static void little(DataOutputStream o, int v, int bytes) throws IOException {
    for (int i = 0; i < bytes; i++) o.write((v >> (8 * i)) & 255);
  }
  @Override
  public void onDestroy() {
    stopCapture();
    if (phone != null && listener != null)
      phone.listen(listener, android.telephony.PhoneStateListener.LISTEN_NONE);
    io.shutdown();
    super.onDestroy();
  }
}
