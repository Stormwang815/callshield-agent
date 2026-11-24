package com.storm.callshield;

import android.app.*;
import android.content.Context;
import android.os.*;

public final class Alerts {
  public static final String RISK = "risk-v2";
  public static final String MIC = "microphone-v2";
  public static void channels(Context c) {
    NotificationManager manager = c.getSystemService(NotificationManager.class);
    NotificationChannel risk =
        new NotificationChannel(RISK, "Call risk alerts", NotificationManager.IMPORTANCE_HIGH);
    risk.enableVibration(true);
    risk.setVibrationPattern(new long[] {0, 200, 150, 200});
    risk.setLockscreenVisibility(Notification.VISIBILITY_PRIVATE);
    manager.createNotificationChannel(risk);
    manager.createNotificationChannel(new NotificationChannel(
        MIC, "User-started microphone analysis", NotificationManager.IMPORTANCE_LOW));
  }
  public static void risk(Context c, String callId, String text) {
    channels(c);
    Notification n = new Notification.Builder(c, RISK)
                         .setSmallIcon(android.R.drawable.ic_dialog_alert)
                         .setContentTitle("Suspicious call signals detected")
                         .setContentText(text)
                         .setStyle(new Notification.BigTextStyle().bigText(text))
                         .setVisibility(Notification.VISIBILITY_PRIVATE)
                         .setAutoCancel(true)
                         .build();
    if (Build.VERSION.SDK_INT < 33
        || c.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
            == android.content.pm.PackageManager.PERMISSION_GRANTED)
      c.getSystemService(NotificationManager.class).notify(callId.hashCode(), n);
  }
}
