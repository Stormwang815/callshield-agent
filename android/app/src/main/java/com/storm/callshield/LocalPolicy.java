package com.storm.callshield;

/** Pure local decision, no network or microphone work on the screening path. */
public final class LocalPolicy {
  public enum Action { ALLOW, SILENCE, REJECT }
  public static Action evaluate(boolean whitelist, boolean spam, long suspiciousUntil, long now) {
    if (whitelist)
      return Action.ALLOW;
    if (spam)
      return Action.REJECT;
    if (suspiciousUntil > now)
      return Action.SILENCE;
    return Action.ALLOW;
  }
  public static String canonical(String value) {
    String cleaned = value.trim().replaceAll("[\\s()\\-]", "");
    if (!cleaned.matches("\\+[1-9][0-9]{6,14}"))
      throw new IllegalArgumentException("Enter a full international number, such as +15555550123");
    return cleaned;
  }
  public static boolean shouldWriteSuspicious(boolean whitelist, String writeback, double risk) {
    return !whitelist && "suspicious".equals(writeback) && Double.isFinite(risk) && risk >= .4
        && risk <= 1;
  }
}
