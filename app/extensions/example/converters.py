"""Example custom converters for command arguments."""

from nextcord.ext import commands


class ChannelOrMemberConverter(commands.Converter):
    """Custom converter checking if input is convertible to Member or TextChannel."""

    async def convert(self, ctx, argument: str):
        member_converter = commands.MemberConverter()
        try:
            member = await member_converter.convert(ctx, argument)
        except commands.MemberNotFound:
            pass
        else:
            return member

        textchannel_converter = commands.TextChannelConverter()
        try:
            channel = await textchannel_converter.convert(ctx, argument)
        except commands.ChannelNotFound:
            pass
        else:
            return channel

        raise commands.BadArgument(f'No Member or TextChannel could be converted from "{argument}"')
