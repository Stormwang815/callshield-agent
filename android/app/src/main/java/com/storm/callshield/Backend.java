package com.storm.callshield;

import android.content.Context;
import java.io.File;
import java.io.IOException;
import java.util.concurrent.TimeUnit;
import okhttp3.*;
import org.json.*;

public final class Backend {
  private final OkHttpClient client = new OkHttpClient.Builder()
                                          .connectTimeout(5, TimeUnit.SECONDS)
                                          .readTimeout(25, TimeUnit.SECONDS)
                                          .callTimeout(30, TimeUnit.SECONDS)
                                          .build();
  private final String base, token;
  public Backend(Context context) {
    var prefs = context.getSharedPreferences("settings", 0);
    base = validateBase(prefs.getString("base", "http://10.0.2.2:8011"));
    token = prefs.getString("token", "");
  }
  public static String validateBase(String value) {
    HttpUrl url = HttpUrl.parse(value.trim());
    if (url == null || !url.username().isEmpty() || !url.password().isEmpty() || url.query() != null
        || url.fragment() != null || !"/".equals(url.encodedPath()))
      throw new IllegalArgumentException(
          "Enter the backend root URL without a path, credentials, or query parameters");
    if (!url.isHttps()
        && !java.util.Arrays.asList("10.0.2.2", "127.0.0.1", "localhost").contains(url.host()))
      throw new IllegalArgumentException(
          "Remote backends require HTTPS; HTTP is limited to local development addresses");
    return url.toString().replaceAll("/$", "");
  }
  public JSONObject json(String method, String path, JSONObject body) throws Exception {
    RequestBody data = body == null
        ? null
        : RequestBody.create(body.toString(), MediaType.get("application/json"));
    return execute(new Request.Builder().url(base + path).method(method, data));
  }
  public JSONObject upload(String callId, int index, File wav) throws Exception {
    RequestBody data = new MultipartBody.Builder()
                           .setType(MultipartBody.FORM)
                           .addFormDataPart("audio", "segment.wav",
                               RequestBody.create(wav, MediaType.get("audio/wav")))
                           .build();
    return execute(new Request.Builder()
            .url(base + "/v1/calls/" + callId + "/segments?index=" + index)
            .post(data));
  }
  private JSONObject execute(Request.Builder request) throws Exception {
    if (!token.trim().isEmpty())
      request.header("Authorization", "Bearer " + token);
    try (Response response = client.newCall(request.build()).execute()) {
      if (!response.isSuccessful())
        throw new IOException("Backend request failed (HTTP " + response.code()
            + "); check the settings or try again later");
      if (response.body() == null)
        throw new IOException("The backend returned an empty response");
      return new JSONObject(response.body().string());
    }
  }
  public static String summaryText(JSONObject result) throws JSONException {
    JSONObject decision = result.getJSONObject("decision");
    String level = decision.optString("risk_level", "UNKNOWN");
    String name = "HIGH".equals(level) ? "High"
        : "MEDIUM".equals(level)       ? "Medium"
        : "LOW".equals(level)          ? "No obvious signals in this segment"
                                         : "Unknown";
    StringBuilder text = new StringBuilder("Risk level: ").append(name);
    if (decision.optBoolean("uncertain", false))
      text.append("\nThe transcript is incomplete or uncertain. Do not assume the call is safe.");
    JSONArray reasons = decision.optJSONArray("reasons");
    if (reasons != null)
      for (int i = 0; i < reasons.length(); i++) text.append("\n• ").append(reasons.getString(i));
    JSONArray tips = decision.optJSONArray("recommended_actions");
    if (tips != null) {
      text.append("\n\nRecommended actions:");
      for (int i = 0; i < tips.length(); i++) text.append("\n• ").append(tips.getString(i));
    }
    JSONArray evidence = result.optJSONArray("evidence");
    if (evidence != null && evidence.length() > 0) {
      text.append("\n\nConversation evidence:");
      for (int i = 0; i < evidence.length(); i++)
        text.append("\n\"").append(evidence.getJSONObject(i).optString("quote")).append("\"");
    }
    return text.toString();
  }
  public static JSONObject numberContext(Context context, String number) throws Exception {
    CallDatabase.NumberEntry entry = number == null || number.trim().isEmpty()
        ? null
        : CallDatabase.get(context).numbers().find(number);
    return new JSONObject()
        .put("is_whitelisted", entry != null && entry.whitelist)
        .put("is_spam", entry != null && entry.confirmedSpam)
        .put("is_suspicious", entry != null && entry.suspiciousUntil > System.currentTimeMillis());
  }
  public static void applyResult(Context c, String number, String callId, JSONObject result)
      throws Exception {
    JSONObject decision = result.getJSONObject("decision");
    if (decision.optBoolean("should_notify", false)) {
      String reason = decision.optJSONArray("reasons") == null
          ? "Verify through an independently located official channel"
          : decision.getJSONArray("reasons").join("; ");
      Alerts.risk(c, callId, reason);
    }
    CallDatabase.applyRisk(c, number, decision.optString("writeback"),
        decision.optDouble("risk_score", 0), decision.optString("risk_level", "UNKNOWN"));
  }
}
