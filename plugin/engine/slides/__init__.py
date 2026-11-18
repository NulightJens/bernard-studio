"""The shared slide maker for the carousel styles.

    from slides import shoot, pictures, captions

shoot     HTML pages -> PNG slides through a hidden browser (Playwright), with every marked text element measured
pictures  frames from his videos at full size, sharp-frame picks and crops that keep burned-in captions out
captions  text detection on finished slides: fails on leftover caption text from his old videos, draws the evidence
"""
