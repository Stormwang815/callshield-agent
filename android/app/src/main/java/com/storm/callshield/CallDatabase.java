package com.storm.callshield;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.room.*;

@Database(entities = {CallDatabase.NumberEntry.class}, version = 1, exportSchema = false)
public abstract class CallDatabase extends RoomDatabase {
  public abstract Numbers numbers();
  private static volatile CallDatabase instance;
  public static CallDatabase get(Context context) {
    if (instance == null)
      synchronized (CallDatabase.class) {
        if (instance == null)
          instance = Room.databaseBuilder(context.getApplicationContext(), CallDatabase.class,
                             "callshield-v2.db")
                         .build();
      }
    return instance;
  }
  @Entity(tableName = "numbers")
  public static class NumberEntry {
    @PrimaryKey @NonNull public String number = "";
    public boolean whitelist;
    public boolean confirmedSpam;
    public long suspiciousUntil;
    public double risk;
    @NonNull public String reason = "";
  }
  @Dao
  public interface Numbers {
    @Query("SELECT * FROM numbers WHERE number=:number") NumberEntry find(String number);
    @Insert(onConflict = OnConflictStrategy.REPLACE) void save(NumberEntry entry);
    @Query("DELETE FROM numbers WHERE number=:number") void delete(String number);
    @Query("UPDATE numbers SET suspiciousUntil=MAX(suspiciousUntil,:until), risk=MAX(risk,:risk), "
           + "reason=:reason WHERE number=:number AND whitelist=0")
    void
    flagExisting(String number, long until, double risk, String reason);
    @Insert(onConflict = OnConflictStrategy.IGNORE) void insertMissing(NumberEntry entry);
  }
  public static void applyRisk(
      Context context, String number, String writeback, double risk, String reason) {
    if (number == null || number.trim().isEmpty())
      return;
    Numbers dao = get(context).numbers();
    NumberEntry entry = dao.find(number);
    if (!LocalPolicy.shouldWriteSuspicious(entry != null && entry.whitelist, writeback, risk))
      return;
    long until = System.currentTimeMillis() + 14L * 24 * 60 * 60 * 1000;
    NumberEntry fresh = new NumberEntry();
    fresh.number = number;
    fresh.suspiciousUntil = until;
    fresh.risk = risk;
    fresh.reason = reason;
    dao.insertMissing(fresh);
    dao.flagExisting(number, until, risk, reason);
  }
}
