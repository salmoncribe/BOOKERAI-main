-- Migration to create the get_available_slots RPC function
-- Run this in your Supabase SQL Editor

create or replace function get_available_slots(
  p_barber_id uuid,
  p_start_date text,
  p_end_date text
)
returns table (
  slot_time timestamptz
)
language plpgsql
as $$
declare
  r_barber record;
  r_override record;
  r_weekly record;
  v_date date;
  v_start_dt timestamp;
  v_end_dt timestamp; 
  v_slot timestamp;
  v_day_of_week text;
  v_duration int;
begin
  -- Get slot duration
  select slot_duration into v_duration from barbers where id = p_barber_id;
  if v_duration is null then v_duration := 60; end if;

  -- Loop through dates
  v_date := p_start_date::date;
  
  while v_date <= p_end_date::date loop
  
    v_start_dt := null;
    v_end_dt := null;

    -- 1. Check Overrides
    select * into r_override from schedule_overrides 
    where barber_id = p_barber_id and date = v_date::text;
    
    if found then
       if not r_override.is_closed then
          v_start_dt := (r_override.date || ' ' || r_override.start_time)::timestamp;
          v_end_dt := (r_override.date || ' ' || r_override.end_time)::timestamp;
       end if;
    else
       -- 2. Check Weekly
       v_day_of_week := lower(trim(to_char(v_date, 'Dy'))); -- "mon"
       
       select * into r_weekly from barber_weekly_hours
       where barber_id = p_barber_id and weekday = v_day_of_week;
       
       if found and not r_weekly.is_closed then
          v_start_dt := (v_date::text || ' ' || r_weekly.start_time)::timestamp;
          v_end_dt := (v_date::text || ' ' || r_weekly.end_time)::timestamp;
       end if;
    end if;

    -- 3. Generate Slots if we have a range
    -- Note: Ensure text format "YYYY-MM-DD HH:MM" is parsed correctly as timestamp
    if v_start_dt is not null and v_end_dt is not null then
       v_slot := v_start_dt;
       
       -- Iterate slots
       while v_slot < v_end_dt loop
          -- Check if booked
          -- appointments.start_time is Text HH:MM, date is Text YYYY-MM-DD
          perform 1 from appointments 
          where barber_id = p_barber_id 
            and date = v_date::text 
            and start_time = to_char(v_slot, 'HH24:MI')
            and status != 'cancelled';
            
          if not found then
             -- Return as UTC TIMESTAMPTZ
             -- We treat the constructed timestamp as being in UTC.
             return next (v_slot at time zone 'UTC'); 
          end if;
          
          v_slot := v_slot + (v_duration || ' minutes')::interval;
       end loop;
    end if;

    v_date := v_date + 1;
  end loop;

  return;
end;
$$;
