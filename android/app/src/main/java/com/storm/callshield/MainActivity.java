package com.storm.callshield;
import android.Manifest;
import android.app.*;
import android.app.role.RoleManager;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.text.InputType;
import android.widget.*;
import java.util.concurrent.*;
import org.json.*;

public class MainActivity extends Activity {
  private final ExecutorService io = Executors.newSingleThreadExecutor();
  private EditText number, text, base, token;
  private TextView output;
  private LinearLayout layout;
  @Override
  public void onCreate(Bundle state) {
    super.onCreate(state);
    Alerts.channels(this);
    ScrollView scroll = new ScrollView(this);
    layout = new LinearLayout(this);
    layout.setOrientation(LinearLayout.VERTICAL);
    layout.setPadding(32, 32, 32, 32);
    scroll.addView(layout);
    setContentView(scroll);
    scroll.setOnApplyWindowInsetsListener((v, insets) -> {
      v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
          insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
      return insets;
    });
    note(
        "CallShield - Call Protection\nLocal screening comes first. Start audio analysis manually. "
        + "Capturing both sides is not guaranteed. A trusted number does not prove identity.");
    button("Enable call screening", () -> {
      if (Build.VERSION.SDK_INT >= 29) {
        RoleManager r = getSystemService(RoleManager.class);
        if (r.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)
            && !r.isRoleHeld(RoleManager.ROLE_CALL_SCREENING))
          startActivityForResult(r.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING), 7);
        else
          show("Call screening is already enabled or unavailable on this device");
      } else
        show("On Android 8/9, check the default-app settings. Call screening is primarily "
             + "validated on Android 10+.");
    });
    number = input("Phone number with country code, e.g. +15555550123", false);
    button("Trust this number", () -> saveNumber("white"));
    button("Confirm spam and block",
        ()
            -> new AlertDialog.Builder(this)
                .setMessage("Future calls from this number will be rejected. Continue?")
                .setPositiveButton("Confirm", (d, w) -> saveNumber("spam"))
                .setNegativeButton("Cancel", null)
                .show());
    button("Check local screening decision", () -> {
      String raw = number.getText().toString();
      task(() -> {
        var e = CallDatabase.get(this).numbers().find(LocalPolicy.canonical(raw));
        show(e == null ? "Unknown number: allowed, but not verified as safe"
                       : LocalPolicy
                             .evaluate(e.whitelist, e.confirmedSpam, e.suspiciousUntil,
                                 System.currentTimeMillis())
                             .name()
                    + " - risk score " + e.risk + " · " + e.reason);
      });
    });
    button("Remove all flags for this number", () -> {
      String raw = number.getText().toString();
      task(() -> {
        CallDatabase.get(this).numbers().delete(LocalPolicy.canonical(raw));
        show("Local flags removed");
      });
    });
    var prefs = getSharedPreferences("settings", 0);
    note("Connection: use http://10.0.2.2:8011 in the emulator. Use HTTPS on a real device. The "
         + "deployment token is shared.");
    base = input("Backend root URL", false);
    base.setText(prefs.getString("base", "http://10.0.2.2:8011"));
    token = input("Access token (optional)", true);
    token.setText(prefs.getString("token", ""));
    button("Save connection settings", () -> {
      try {
        String u = Backend.validateBase(base.getText().toString());
        prefs.edit()
            .putString("base", u)
            .putString("token", token.getText().toString().trim())
            .apply();
        show("Connection settings saved");
      } catch (Exception e) {
        show(e.getMessage());
      }
    });
    note("The text demo displays results without changing real-number lists.");
    text = input("Demo conversation", false);
    text.setMinLines(3);
    text.setText("This is bank support. Your account is locked. Transfer money now and tell me "
                 + "your verification code.");
    button("Analyze text using the backend", () -> {
      String t = text.getText().toString();
      String raw = number.getText().toString();
      task(() -> {
        JSONObject req = new JSONObject()
                             .put("transcript", t)
                             .put("source_type", "text_demo")
                             .put("number_context",
                                 Backend.numberContext(this,
                                     raw.trim().isEmpty() ? null : LocalPolicy.canonical(raw)));
        show(Backend.summaryText(new Backend(this).json("POST", "/v1/analyze", req)));
      });
    });
    button("Start microphone analysis (up to 60 seconds)", () -> {
      if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
          != PackageManager.PERMISSION_GRANTED) {
        requestPermissions(
            new String[] {Manifest.permission.RECORD_AUDIO, Manifest.permission.READ_PHONE_STATE},
            20);
        show("Grant permission, then tap Start again");
        return;
      }
      if (Build.VERSION.SDK_INT >= 33
          && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
              != PackageManager.PERMISSION_GRANTED) {
        requestPermissions(new String[] {Manifest.permission.POST_NOTIFICATIONS}, 21);
        show("Confirm notification permission, then tap Start again");
        return;
      }
      new AlertDialog.Builder(this)
          .setTitle("Recording and upload consent")
          .setMessage("Capture microphone audio and upload it to your configured backend for up to "
                      + "60 seconds. Both sides may not be captured. The backend retains "
                      + "transcripts and results; an optional semantic model receives transcripts. "
                      + "Obtain participant consent.")
          .setPositiveButton("Agree and start",
              (d, w) -> {
                try {
                  String n = number.getText().toString().trim();
                  if (!n.trim().isEmpty())
                    n = LocalPolicy.canonical(n);
                  startForegroundService(
                      new Intent(this, MicrophoneService.class).putExtra("number", n));
                  show("Analysis started. Stop it using the notification or the Stop button.");
                } catch (Exception e) {
                  show(e.getMessage());
                }
              })
          .setNegativeButton("Cancel", null)
          .show();
    });
    button("Stop microphone analysis",
        () -> startService(new Intent(this, MicrophoneService.class).setAction("STOP")));
    button("View the latest analysis", () -> show(prefs.getString("last_status", "Not started")));
    button("Delete the latest backend call record", () -> {
      String id = prefs.getString("last_call", "");
      task(() -> {
        if (id.trim().isEmpty()) {
          show("No call record is available");
          return;
        }
        new Backend(this).json("DELETE", "/v1/calls/" + id, null);
        prefs.edit().remove("last_call").putString("last_status", "Backend record deleted").apply();
        show("Backend record deleted. Remove local number flags separately if needed.");
      });
    });
    output = new TextView(this);
    output.setTextIsSelectable(true);
    layout.addView(output);
    show(prefs.getString("last_status", "Ready"));
  }
  private void saveNumber(String kind) {
    String raw = number.getText().toString();
    task(() -> {
      var e = new CallDatabase.NumberEntry();
      e.number = LocalPolicy.canonical(raw);
      e.whitelist = "white".equals(kind);
      e.confirmedSpam = "spam".equals(kind);
      e.reason = "Manually confirmed by the user";
      CallDatabase.get(this).numbers().save(e);
      show("Saved: " + kind);
    });
  }
  private EditText input(String hint, boolean password) {
    EditText e = new EditText(this);
    e.setHint(hint);
    if (password)
      e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
    layout.addView(e);
    return e;
  }
  private void note(String s) {
    TextView v = new TextView(this);
    v.setText(s);
    v.setPadding(0, 20, 0, 12);
    layout.addView(v);
  }
  private void button(String title, Runnable action) {
    Button b = new Button(this);
    b.setText(title);
    b.setOnClickListener(v -> action.run());
    layout.addView(b);
  }
  interface Work {
    void run() throws Exception;
  }
  private void task(Work work) {
    io.execute(() -> {
      try {
        work.run();
      } catch (Exception e) {
        show(e.getMessage() == null ? "Operation failed" : e.getMessage());
      }
    });
  }
  private void show(String value) {
    runOnUiThread(() -> {
      if (output != null)
        output.setText(value);
    });
  }
  @Override
  public void onDestroy() {
    io.shutdown();
    super.onDestroy();
  }
}
