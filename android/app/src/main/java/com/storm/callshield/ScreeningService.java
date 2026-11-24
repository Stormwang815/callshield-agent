package com.storm.callshield;

import android.os.*;
import android.telecom.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

public class ScreeningService extends CallScreeningService {
  private final ExecutorService io = Executors.newSingleThreadExecutor();
  private final Handler main = new Handler(Looper.getMainLooper());
  @Override
  public void onScreenCall(Call.Details details) {
    if (Build.VERSION.SDK_INT >= 29
        && details.getCallDirection() != Call.Details.DIRECTION_INCOMING)
      return;
    AtomicBoolean responded = new AtomicBoolean();
    Runnable fallback = () -> answer(details, LocalPolicy.Action.ALLOW, responded);
    main.postDelayed(fallback, 1500);
    io.execute(() -> {
      LocalPolicy.Action result = LocalPolicy.Action.ALLOW;
      try {
        String raw = details.getHandle() == null ? "" : details.getHandle().getSchemeSpecificPart();
        String number = LocalPolicy.canonical(raw);
        CallDatabase.NumberEntry entry = CallDatabase.get(this).numbers().find(number);
        if (entry != null)
          result = LocalPolicy.evaluate(entry.whitelist, entry.confirmedSpam, entry.suspiciousUntil,
              System.currentTimeMillis());
      } catch (Exception ignored) { /* Unknown number or failed local lookup: allow. */
      }
      LocalPolicy.Action decided = result;
      main.post(() -> {
        main.removeCallbacks(fallback);
        answer(details, decided, responded);
      });
    });
  }
  private void answer(Call.Details details, LocalPolicy.Action action, AtomicBoolean once) {
    if (!once.compareAndSet(false, true))
      return;
    CallResponse.Builder response = new CallResponse.Builder()
                                        .setDisallowCall(action == LocalPolicy.Action.REJECT)
                                        .setRejectCall(action == LocalPolicy.Action.REJECT)
                                        .setSkipCallLog(false)
                                        .setSkipNotification(false);
    if (Build.VERSION.SDK_INT >= 29)
      response.setSilenceCall(action == LocalPolicy.Action.SILENCE);
    android.util.Log.i("CallShieldScreening", "decision=" + action.name());
    respondToCall(details, response.build());
  }
  @Override
  public void onDestroy() {
    io.shutdownNow();
    super.onDestroy();
  }
}
