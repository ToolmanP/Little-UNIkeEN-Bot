from abc import ABC, abstractmethod
from typing import Union, Tuple, Any, List
from utils.basicEvent import send, warning, readGlobalConfig, writeGlobalConfig, getGroupAdmins

class StandardPlugin(ABC):
    @abstractmethod
    def judgeTrigger(self, msg:str, data:Any) -> bool:
        """
        @msg: message text
        @data: all the message data, including group_id or user_id
        @return: whether trigger this class
        """
        raise NotImplementedError
    
    @abstractmethod
    def executeEvent(self, msg:str, data:Any) -> Union[None, str]:
        """
        @msg: message text
        @data: all the message data, including group_id or user_id
        @return:
            if None, then continue tranversing following plugins
            if "OK", then stop tranversing
        """
        raise NotImplementedError

    @abstractmethod
    def getPluginInfo(self)->dict:
        """
        @return:
            a dict object like:
            {
                'name': 'Faq',                      # require
                'description': '问答库',             # require
                'commandDescription': '问 [title]', # require
                'usePlace': ['group', 'private', ], # require
                'showInHelp': True,                 # suggest, default True
                'pluginConfigTableNames': ['Faq',], # suggest, must be unique among plugins
                'version': '1.0.0',                 # suggest
                'author': 'Unicorn',                # suggest
                ...                                 # any other information you want
            }
        """
        raise NotImplementedError
class RecallMessageStandardPlugin(ABC):
    @abstractmethod
    def recallMessage(self, data:Any)->Union[str, None]:
        raise NotImplementedError

class GroupUploadStandardPlugin(ABC):
    @abstractmethod
    def uploadFile(self, data)->Union[str, None]:
        raise NotImplementedError

class PluginGroupManager(StandardPlugin):
    def __init__(self, plugins:List[StandardPlugin], groupName: str, groupInfo:dict = {}) -> None:
        self.plugins = plugins
        self.groupName = groupName
        self.readyPlugin = None
        self.enabledDict = readGlobalConfig(None, groupName+'.enable')
        self.defaultEnabled = False
        self.groupInfo = groupInfo
        self._checkGroupInfo()

    def _checkGroupInfo(self):
        # check group name
        if 'name' not in self.groupInfo.keys():
            self.groupInfo['name'] = self.groupName
        # check description
        if 'description' not in self.groupInfo.keys():
            description = ''
            for p in self.plugins:
                description += p.getPluginInfo()['description'] + '/'
            description = description[:-1]
            self.groupInfo['description'] = description
        # check command descrption
        if 'commandDescription' not in self.groupInfo.keys():
            commandDescription = ''
            for p in self.plugins:
                commandDescription += p.getPluginInfo()['commandDescription'] + '/'
            commandDescription = commandDescription[:-1]
            self.groupInfo['commandDescription'] = commandDescription
        # check use place
        if not all(['group' in p.getPluginInfo()['usePlace'] for p in self.plugins]):
            warning('all plugins should be able to use in group, error in {}'.format(self.groupName))
        self.groupInfo['usePlace'] = ['group']

    def judgeTrigger(self, msg:str, data:Any)->bool:
        userId = data['user_id']
        groupId = data['group_id']
        if msg == '-grpcfg enable %s'%self.groupName and userId in getGroupAdmins(groupId):
            self.readyPlugin = 'enable'
            return True
        if msg == '-grpcfg disable %s'%self.groupName and userId in getGroupAdmins(groupId):
            self.readyPlugin = 'disable'
            return True
        if not self.queryEnabled(groupId):
            return False
        for plugin in self.plugins:
            if plugin.judgeTrigger(msg, data):
                self.readyPlugin = plugin
                return True
        return False
    def executeEvent(self, msg:str, data:Any)->Union[None, str]:
        if self.readyPlugin == None:
            warning("logic error in PluginGroupManager: executeEvent self.readyPlugin == None")
            return None
        if self.readyPlugin in ['enable', 'disable']:
            enabled = self.readyPlugin == 'enable'
            self.readyPlugin = None
            groupId = data["group_id"]
            if self.queryEnabled(groupId) != enabled:
                writeGlobalConfig(groupId, self.groupName + '.enable', enabled)
                self.enabledDict[groupId] = enabled
            send(data['group_id'], "OK")
            return "OK"
        else:
            try:
                result = self.readyPlugin.executeEvent(msg, data)
                self.readyPlugin = None
                return result
            except Exception as e:
                warning("logic error in PluginGroupManager [{}]: {}".format(self.groupName, e))
                return None
    def getPluginInfo(self, )->dict:
        return self.groupInfo
    def queryEnabled(self, groupId: int)->bool:
        if groupId not in self.enabledDict.keys():
            writeGlobalConfig(groupId, self.groupName, {'name':self.groupName, 'enable': self.defaultEnabled})
            self.enabledDict[groupId] = self.defaultEnabled
        return self.enabledDict[groupId]
    def getPlugins(self)->List[StandardPlugin]:
        return self.plugins