from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0016_focus_monitor"),
    ]

    operations = [
        migrations.AddField(
            model_name="learningrecord",
            name="video_playthrough_acknowledged",
            field=models.BooleanField(
                default=False,
                help_text="必修视频课：须由播放到结尾（本地/直链）或学员确认（嵌入视频）后，才允许标记学完。",
                verbose_name="已确认完整观看视频",
            ),
        ),
    ]
